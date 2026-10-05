// npm run test:browser. Requires Playwright Chromium, or PALERMO_BROWSER_EXECUTABLE.
const { test, before, after } = require('node:test');
const assert = require('node:assert/strict');
const { chromium, webkit } = require('playwright');
const { spawn } = require('node:child_process');
const { mkdtemp, rm } = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
let server, browser, temp;
const port = process.env.PALERMO_TEST_PORT || 8034;
const origin = `http://127.0.0.1:${port}`;

before(async () => {
  temp = await mkdtemp(path.join(os.tmpdir(), 'palermo-browser-'));
  server = spawn(process.env.PALERMO_PYTHON || '.venv/bin/python', ['-m','uvicorn','tests.browser.server:app','--host','127.0.0.1','--port',port], {
    env: {...process.env, PALERMO_DB_PATH:path.join(temp,'games.sqlite3')}, stdio:['ignore','ignore','pipe']
  });
  let errors=''; server.stderr.on('data', b=>errors+=b);
  let ready=false;
  for(let i=0;i<100;i++) {
    try { if((await fetch(`${origin}/health`)).ok){ready=true;break;} } catch {}
    await new Promise(r=>setTimeout(r,100));
  }
  assert.ok(ready,errors);
  browser = await (process.env.PALERMO_BROWSER === 'webkit' ? webkit : chromium).launch({headless:true, executablePath:process.env.PALERMO_BROWSER_EXECUTABLE || undefined});
}, {timeout:20000});
after(async()=>{await browser?.close(); if(server && server.exitCode === null) {server.kill('SIGTERM'); await new Promise(r=>server.once('exit',r));} if(temp) await rm(temp,{recursive:true,force:true});});

async function page(view, viewport={width:1066,height:1552}) {
  const page=await browser.newPage({viewport,reducedMotion:'reduce'});
  await page.goto(`${origin}/browser-fixture?view=${view}`);
  await page.waitForFunction(()=>window.fixtureReady);
  return page;
}
async function choose(page,id,player) {
  const picker=page.locator(`#${id}`).locator('..');
  await picker.locator('.player-picker-button').click();
  await picker.locator(`[data-player-value="${player}"]`).click();
}

test('voting picker receives the real pointer above player cards and persists selections', async()=>{
  const p=await page('vote');
  try {
    if(process.env.PALERMO_REPRO_OLD_CSS) {await p.addStyleTag({content:'.vote-decision-panel {position:static!important; z-index:auto!important;}'});p.setDefaultTimeout(4000);}
    await p.locator('[data-target="P2"]').click();
    await choose(p,'trusted-player','P5');
    await choose(p,'second-suspect','P3');
    assert.equal(await p.locator('#trusted-player').inputValue(),'P5');
    assert.equal(await p.locator('#confirm-vote').isEnabled(),true);
    await p.reload(); await p.waitForFunction(()=>window.fixtureReady);
    assert.equal(await p.locator('#trusted-player').inputValue(),'P5');
    assert.equal(await p.locator('#second-suspect').inputValue(),'P3');
    assert.equal(await p.locator('[data-target="P2"]').getAttribute('class'),'target-card is-selected');
  } finally {await p.close();}
});

test('long answer remains scrollable and submit is clickable on a narrow screen', async()=>{
  const p=await page('answer',{width:390,height:700});
  try {
    await p.locator('#human-text').fill('پاسخ من');
    let submitted;
    await p.evaluate(()=>{submitAndAdvance=async payload=>window.lastSubmitted=payload;});
    await p.locator('#submit-speech').click();
    submitted=await p.evaluate(()=>window.lastSubmitted);
    assert.equal(submitted.action,'ANSWER');
    assert.ok(await p.locator('.question-list').evaluate(el=>el.scrollHeight>el.clientHeight));
    assert.ok(await p.locator('#submit-speech').evaluate(el=>{
      const r=el.getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight;
    }));
  } finally {await p.close();}
});

test('typed draft and portrait mention survive reload; home preserves the game', async()=>{
  const p=await page('discussion',{width:390,height:700});
  try {
    await p.locator('#human-text').fill('سلام @Rosa');
    await p.locator('[data-mention-player="P3"]').click();
    const draft=await p.locator('#human-text').inputValue();
    assert.ok(draft.includes('Rosa Greco'));
    await p.reload(); await p.waitForFunction(()=>window.fixtureReady);
    assert.equal(await p.locator('#human-text').inputValue(),draft);
    await p.locator('#story-screen [data-go-home]').click();
    assert.equal(await p.locator('#resume-game').isVisible(),true);
    assert.ok(await p.evaluate(()=>!!localStorage.getItem(SESSION_KEY)));
  } finally {await p.close();}
});

test('fetch header and body stalls time out, preserving the draft and unlocking the form', async()=>{
  const p=await page('answer');
  try {
    await p.locator('#human-text').fill('متن محفوظ');
    const result=await p.evaluate(async()=>{
      const realFetch=window.fetch, bounded=fetchWithTimeout;
      let timed=0;
      window.fetch=()=>new Promise(()=>{});
      try{await bounded('/stall',{},30);}catch{timed++;}
      window.fetch=async()=>({ok:true,text:()=>new Promise(()=>{})});
      try{await bounded('/stall-body',{},30);}catch{timed++;}
      window.fetch=()=>new Promise(()=>{});
      fetchWithTimeout=(url,options)=>bounded(url,options,40);
      await submitAndAdvance({action:'ANSWER',text:$('#human-text').value},'play_wait',5);
      window.fetch=realFetch;
      return {timed,locked:actionInFlight,draft:readStored(SESSION_KEY,{}).drafts};
    });
    assert.equal(result.timed,2); assert.equal(result.locked,false);
    assert.ok(Object.values(result.draft).some(d=>d.text==='متن محفوظ'));
  } finally {await p.close();}
});

test('human plays a complete offline match through the real UI and API', {timeout:90000}, async()=>{
  const p=await browser.newPage({viewport:{width:1280,height:900},reducedMotion:'reduce'});
  try {
    await p.route('**/games/interactive', route=>{
      const body=route.request().postDataJSON(); body.ai_mode='offline';
      return route.continue({postData:JSON.stringify(body)});
    });
    await p.goto(`${origin}/ui/`);
    await p.locator('#new-game').click(); await p.locator('[data-character="1"]').click();
    await p.waitForFunction(()=>state.stage==='role');
    let reloaded=false;
    for(let i=0;i<220;i++) {
      const stage=await p.evaluate(()=>state.stage);
      if(stage==='game_over') break;
      if(stage==='stopped') throw new Error(await p.evaluate(()=>JSON.stringify(state.run)));
      if(stage==='human_discussion') {
        await p.locator('#human-text').fill('I am checking the public claims and votes.');
        if(!reloaded){await p.reload();await p.waitForFunction(()=>state.stage==='human_discussion');reloaded=true;assert.equal(await p.locator('#human-text').inputValue(),'I am checking the public claims and votes.');}
        await p.locator('#submit-speech').click();
      } else if(stage==='vote') {
        const ids=await p.locator('[data-target]').evaluateAll(es=>es.map(e=>e.dataset.target));
        await p.locator(`[data-target="${ids[0]}"]`).click();
        await choose(p,'trusted-player',ids[1]);
        if(await p.locator('#second-suspect').count()) await choose(p,'second-suspect',ids[2]);
        await p.locator('#confirm-vote').click();
      } else {
        const next=p.locator('#story-content button:visible:enabled').first();
        if(await next.count()) await next.click();
        else await p.waitForTimeout(150);
      }
      await p.waitForTimeout(40);
    }
    assert.equal(await p.evaluate(()=>state.stage),'game_over');
    assert.ok(await p.evaluate(()=>['CITIZEN','MAFIA'].includes(state.public.winner)));
    assert.equal(await p.evaluate(()=>completedReports().length),1);
  } finally {await p.close();}
});

test('lost action response recovers from the receipt without sending the action twice', {timeout:30000}, async()=>{
  const p=await browser.newPage({viewport:{width:1280,height:900},reducedMotion:'reduce'});
  try {
    await p.route('**/games/interactive', route=>route.continue({postData:JSON.stringify({...route.request().postDataJSON(),ai_mode:'offline'})}));
    await p.goto(`${origin}/ui/`);
    await p.locator('#new-game').click(); await p.locator('[data-character="1"]').click();
    await p.locator('#role-next').click();
    await p.waitForFunction(()=>state.stage==='claim');
    let submissions=0;
    await p.route('**/interactive/action', async route=>{submissions++; await route.fetch(); await route.abort('connectionfailed');});
    await p.locator('[data-claim="CITIZEN"]').click();
    await p.waitForFunction(()=>!actionInFlight && !state.pendingAction && state.public.role_claims.P1==='CITIZEN');
    assert.equal(submissions,1);
    const claims=await p.evaluate(()=>state.events.filter(e=>e.type==='ROLE_CLAIMED' && e.actor==='P1'));
    assert.equal(claims.length,1);
    await p.reload();
    await p.waitForFunction(()=>state.gameId && !['home','restoring'].includes(state.stage));
    assert.equal(submissions,1);
    assert.equal(await p.evaluate(()=>state.public.role_claims.P1),'CITIZEN');
  } finally {await p.close();}
});

test('public position shows its portrait and postgame night review reveals the actual targets', async()=>{
  const p=await page('discussion');
  try {
    await p.evaluate(()=>{
      showDiscussionEvent({event_id:'statement',type:'PLAYER_SPOKE',actor:'P3',round:2,text:'یک فرضیه دارم.',position:{target:'P4',reason:'شواهد هنوز قطعی نیست.',evidence_ids:[]}});
    });
    await p.locator('.dialogue-copy .player-reference').waitFor();
    assert.ok((await p.locator('.dialogue-copy').innerText()).includes('Marco Conti'));
    assert.ok(await p.locator('.dialogue-copy img').count());
    await p.evaluate(()=>{
      state.public.phase='GAME_OVER'; state.public.winner='CITIZEN';
      state.events=[{event_id:'night',type:'NIGHT_RESULT',result:'NO_DEATH',round:2,visibility:'PUBLIC'}];
      state.nightReplay=[{round:2,reason:'PROTECTED',attacker:'P7',attack_target:'P3',protected_target:'P3',doctor:'P5'}];
      showGameOver();
    });
    await p.locator('#review-nights').click();
    await p.locator('.journal-night summary').click();
    const detail=await p.locator('.journal-replay').textContent();
    assert.ok(detail.includes('حفاظت موفق') && /Rosa\s+Greco/.test(detail), detail);
    assert.ok(detail.includes('هدف حمله') && detail.includes('هدف حفاظت'));
    await p.evaluate(()=>{state.public.phase='DAY_DISCUSSION';renderFacts();});
    assert.equal(await p.locator('.journal-replay').count(),0);
  } finally {await p.close();}
});

for (const viewport of [{width:390,height:700},{width:844,height:390}]) {
  test(`mobile vote ordering, optional inputs and excluded targets at ${viewport.width}x${viewport.height}`, async()=>{
    const p=await page('vote',viewport);
    try {
      assert.equal(await p.locator('#second-suspect').locator('..').locator('.player-picker-button').isDisabled(),true);
      assert.equal(await p.locator('#trusted-player').locator('..').locator('.player-picker-button').isDisabled(),true);
      await p.locator('[data-target="P2"]').click();
      assert.equal(await p.locator('#confirm-vote').isEnabled(),true);
      assert.equal(await p.locator('#trusted-player option[value="P2"]').evaluate(e=>e.hidden&&e.disabled),true);
      await choose(p,'second-suspect','P3');
      assert.equal(await p.locator('#trusted-player option[value="P3"]').evaluate(e=>e.hidden),true);
      await p.locator('[data-target="P3"]').click();
      assert.equal(await p.locator('#second-suspect').inputValue(),'');
      const labels=await p.locator('.vote-decision-panel label').allTextContents();
      assert.ok(labels[0].includes('مظنون دوم'));
      await p.evaluate(()=>{submitAndAdvance=async payload=>window.lastSubmitted=payload;});
      await p.locator('#confirm-vote').click();
      assert.deepEqual(await p.evaluate(()=>window.lastSubmitted),{action:'SUBMIT_VOTE_DECISION',vote_target:'P3'});
      await p.evaluate(()=>{state.private.role='MAFIA_BOSS';state.private.faction='MAFIA';showVote();});
      assert.equal(await p.locator('#trusted-player, #second-suspect').count(),0);
      await p.locator('[data-target="P2"]').click();
      await p.locator('#confirm-vote').click();
      assert.deepEqual(await p.evaluate(()=>window.lastSubmitted),{action:'SUBMIT_VOTE_DECISION',vote_target:'P2'});
    } finally {await p.close();}
  });
}

test('dead human watches without role actions, while temporary shunning stays reversible',async()=>{
  const p=await page('vote',{width:390,height:700});
  try {
    await p.evaluate(()=>{state.public.players.P1.alive=false;state.public.phase='NIGHT_ACTION';state.availableActions=[];state.run.status='RUNNING';routePlay();});
    assert.ok((await p.locator('#story-content').textContent()).includes('تماشای بازی'));
    assert.equal(await p.locator('#confirm-vote, #trusted-player').count(),0);
    await p.evaluate(()=>{state.public.players.P1.alive=true;state.public.players.P1.shunned=true;state.private.shunned=true;showNight();});
    assert.ok(!(await p.locator('#story-content').textContent()).includes('تماشای بازی'));
  } finally {await p.close();}
});
