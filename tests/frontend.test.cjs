// Run with: node --test tests/frontend.test.cjs
// Exercise the shipped controller and render functions with a small DOM adapter.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../Frontend/app.js'), 'utf8');
const bootstrap = source.lastIndexOf('$("#new-game").addEventListener');

test('answer view exposes the response action and uses a scrollable question area', async () => {
  await harness().run(`
    state.lang='fa'; state.public.round=2;
    state.events=[
      {type:'PLAYER_ASKED',round:2,visibility:'PUBLIC',actor:'P4',target:'P1',question_id:'q1',text:'پرسش اول '.repeat(30)},
      {type:'PLAYER_ASKED',round:2,visibility:'PUBLIC',actor:'P5',target:'P1',question_id:'q2',text:'پرسش دوم '.repeat(30)},
    ];
    showHumanDiscussion(['ANSWER']);
    const content=$('#story-content');
    assert.ok(content.className.includes('scrollable-form'));
    assert.ok(content.innerHTML.includes('class="question-list"'));
    assert.equal((content.innerHTML.match(/class="question-card"/g)||[]).length,2);
    assert.ok(content.innerHTML.includes('id="submit-speech"'));
    assert.ok(content.innerHTML.includes('ثبت پاسخ'));
    assert.equal($('#slide-name').textContent,'بحث شهر');
    assert.equal($('#slide-round').textContent,'روز 2');
    assert.equal($('#scene-label').textContent,'مرحلهٔ فعلی');
  `);
});

test('typing @ offers portraits and inserts the selected player at the caret', async () => {
  await harness().run(`
    state.lang='fa';
    assert.equal(activeMention('email@site',10),null);
    assert.equal(activeMention('سلام @Rosa',10).query,'Rosa');
    const original='سلام @Ro، نظرت چیست؟';
    const mention=activeMention(original,8);
    const selected=insertPlayerMention(original,mention,'Rosa Greco');
    assert.equal(selected.value,'سلام @Rosa Greco، نظرت چیست؟');
    assert.equal(selected.value.slice(selected.caret),'، نظرت چیست؟');
    showHumanDiscussion(['ANSWER']);
    const input=$('#human-text');
    const menu=$('#player-mentions');
    input.value='@Rosa'; input.selectionStart=5; input.selectionEnd=5;
    input.handlers.input();
    assert.equal(menu.hidden,false);
    assert.ok(menu.innerHTML.includes('Rosa Greco'));
    assert.ok(menu.innerHTML.includes('Profile_Character_'));
    assert.ok(!menu.innerHTML.includes('Luca Romano'));
    assert.ok($('#story-content').innerHTML.includes('برای انتخاب بازیکن @ بزن'));
  `);
});

test('player names in prose resolve to the right portraits without matching word fragments', async () => {
  await harness().run(`
    state.lang='fa';
    const matches=playerNameMatches('از Marco Conti پرسیدم و النا و Rosa را دیدم؛ روزانه خبری نبود.');
    assert.deepEqual(Array.from(matches,({name,id})=>[name,id]),[
      ['Marco Conti','P4'],['النا','P7'],['Rosa','P3'],
    ]);
    state.playerNames.P4='Marco & Co';
    assert.equal(playerNameMatches('Marco & Co')[0].id,'P4');
    state.playerNames={}; state.characterMap=buildCharacterMap(4);
    assert.equal(playerNameMatches('مارکو')[0].id,'P1');
    assert.equal(playerNameMatches('النا')[0].id,'P7');
  `);
});

test('journal header shows only the current player with the real role', async () => {
  await harness().run(`
    state.lang='fa';
    state.private.role='DOCTOR';
    state.public.role_claims={P1:'CITIZEN',P2:'DETECTIVE'};
    let html=renderJournalPlayer();
    assert.equal((html.match(/facts-player-photo/g)||[]).length,1);
    assert.ok(html.includes('Matteo Ricci') && html.includes('پزشک'));
    assert.ok(!html.includes('Vittorio Moretti') && !html.includes('کارآگاه'));
    assert.ok(!renderTimeline().includes('journal-roster'));
    state.playerNames.P1='<script>bad</script>';
    assert.ok(!renderJournalPlayer().includes('<script>'));
    state.private=null;
    assert.equal(renderJournalPlayer(),'');
  `);
});

test('private tab keeps trust for citizens but hides it for mafia, and never shows notes', async () => {
  await harness().run(`
    state.lang='fa';
    state.notes.text='private note';
    state.private.trust={P2:73};
    for (const role of ['CITIZEN','DOCTOR','DETECTIVE']) {
      state.private.role=role;
      const html=renderPrivateIntel();
      assert.ok(html.includes('data-journal-key="trust"'));
      assert.ok(html.includes('Vittorio Moretti'));
      assert.ok(!html.includes('private note') && !html.includes('data-journal-key="notes"'));
    }
    for (const role of ['MAFIA_BOSS','MAFIA_DEPUTY']) {
      state.private.role=role;
      state.private.faction='MAFIA';
      state.private.mafia_private_information={partner:'P2'};
      const html=renderPrivateIntel();
      assert.ok(!html.includes('data-journal-key="trust"'));
      assert.ok(!html.includes('trust-meter') && !html.includes('private note'));
      assert.ok(!html.includes('data-journal-key="notes"'));
      assert.ok(html.includes('mafia-partner'));
    }
  `);
});

test('journal groups complete vote tables and night restrictions without technical noise', async () => {
  const h = harness();
  await h.run(`
    state.lang='fa';
    state.events=[
      {round:1,visibility:'PUBLIC',type:'VOTE_CAST',actor:'P1',target:'P3'},
      {round:1,visibility:'PUBLIC',type:'VOTE_CAST',actor:'P2',target:'P3'},
      {round:1,visibility:'PUBLIC',type:'VOTE_CAST',actor:'P3',target:'P1'},
      {round:1,visibility:'PUBLIC',type:'PLAYER_SHUNNED',player:'P3'},
      {round:1,visibility:'PUBLIC',type:'NIGHT_STARTED'},
      {round:1,visibility:'PUBLIC',type:'NIGHT_RESULT',result:'NO_DEATH'},
      {round:1,visibility:'PRIVATE',type:'TRUST_UPDATED',text:'secret trust'},
      {round:1,visibility:'ENGINE',type:'NIGHT_RESOLUTION',text:'secret cause'},
      {round:2,visibility:'PUBLIC',type:'DISCUSSION_STARTED'},
    ];
    const html=renderTimeline();
    assert.ok(html.indexOf('روز 2') < html.indexOf('روز 1'));
    assert.equal((html.match(/<tr>/g)||[]).length,4);
    assert.ok(html.includes('Rosa Greco: 2'));
    assert.ok(html.includes('هدف مجاز استعلام'));
    for(const hidden of ['secret trust','secret cause','TRUST UPDATED','NIGHT STARTED']) assert.ok(!html.includes(hidden));
  `);
});

test('journal links batch answers once and hides only exact repeated speech', async () => {
  const h=harness();
  await h.run(`
    state.lang='fa';
    const base={round:1,visibility:'PUBLIC'};
    state.events=[
      {...base,type:'PLAYER_ASKED',actor:'P1',target:'P3',question_id:'q1',text:'پرسش اول'},
      {...base,type:'PLAYER_ASKED',actor:'P2',target:'P3',question_id:'q2',text:'پرسش دوم'},
      {...base,type:'PLAYER_SPOKE',actor:'P3',text:'جواب مشترک'},
      {...base,type:'PLAYER_ANSWERED',actor:'P3',targets:['P1','P2'],question_ids:['q1','q2'],event_id:'a1',text:'جواب مشترک'},
      {...base,type:'PLAYER_ASKED',actor:'P4',target:'P2',question_id:'q3',text:'<script>bad</script>'},
    ];
    const html=renderTimeline();
    assert.equal((html.match(/جواب مشترک/g)||[]).length,1);
    assert.ok(html.includes('پرسش اول') && html.includes('پرسش دوم'));
    assert.ok(html.includes('منتظر پاسخ'));
    assert.ok(!html.includes('<script>'));
    assert.equal(state.events.length,5);
  `);
});

test('journal distinguishes public uncertainty, postgame replay and missing old evidence', async () => {
  const h=harness();
  await h.run(`
    state.lang='fa';
    state.events=[{round:1,visibility:'PUBLIC',type:'NIGHT_RESULT',result:'NO_DEATH'}];
    state.nightReplay=[{round:1,reason:'PROTECTED',attack_target:'P2',protected_target:'P2'}];
    assert.ok(!renderTimeline().includes('حفاظت موفق'));
    assert.ok(renderTimeline().includes('علت دقیق برای عموم'));
    state.public.phase='GAME_OVER';
    assert.ok(renderTimeline().includes('حفاظت موفق'));
    assert.ok(renderTimeline().includes('Vittorio Moretti'));
    state.nightReplay=[];
    assert.ok(renderTimeline().includes('نسخهٔ قدیمی'));
  `);
});

test('journal merges elimination and reveal, omits empty wills and marks false claims', async () => {
  const h=harness();
  await h.run(`
    state.lang='fa';
    state.public.role_claims={P3:'DETECTIVE'};
    state.public.revealed_roles={P3:'MAFIA_DEPUTY'};
    const base={round:2,visibility:'PUBLIC'};
    state.events=[
      {...base,type:'VOTE_CAST',actor:'P1',target:'P3'},
      {...base,type:'PLAYER_ELIMINATED',player:'P3'},
      {...base,type:'ROLE_REVEALED',player:'P3',role:'MAFIA_DEPUTY'},
      {...base,type:'WILL_REVEALED',player:'P3',text:''},
    ];
    const html=renderJournal();
    assert.equal((html.match(/معاون مافیا/g)||[]).length,1);
    assert.ok(!html.includes('وصیت'));
    assert.ok(renderClaims().includes('ناسازگار'));
  `);
});

test('claims live in private tab and mafia scenario uses only private strategy', async () => {
  await harness().run(`
    state.lang='fa';
    state.public.role_claims={P1:'CITIZEN',P2:'DETECTIVE'};
    assert.ok(!renderTimeline().includes('ادعاهای ثبت‌شده'));
    let html=renderPrivateIntel();
    assert.ok(html.includes('ادعاهای ثبت‌شده'));
    assert.ok(html.includes('Matteo Ricci') && html.includes('Vittorio Moretti'));
    assert.ok(!html.includes('نقش واقعی') && !html.includes('سناریوی مافیا'));
    state.private={role:'MAFIA_BOSS',faction:'MAFIA',trust:{P2:90},investigations:[],mafia_private_information:{partner:'P2',strategy:'CREATE_TWO_SIDES'}};
    html=renderPrivateIntel();
    assert.ok(html.includes('سناریوی مافیا') && html.includes('ساختن دو جبهه'));
    assert.ok(html.includes('ادعاهای ثبت‌شده'));
    assert.ok(!html.includes('نقش واقعی') && !html.includes('data-journal-key="trust"'));
    assert.ok(!renderTimeline().includes('ساختن دو جبهه'));
    state.private.role='MAFIA_DEPUTY';
    assert.ok(renderPrivateIntel().includes('ساختن دو جبهه'));
    state.private.mafia_private_information.strategy=null;
    assert.ok(renderPrivateIntel().includes('هنوز انتخاب نشده است'));
    state.private.role='DOCTOR'; state.private.faction='CITIZEN';
    state.private.mafia_private_information.strategy='CREATE_TWO_SIDES';
    assert.ok(!renderPrivateIntel().includes('سناریوی مافیا'));
  `);
});

test('dialogue hides technical event IDs without changing the stored evidence', async () => {
  const h=harness();
  await h.run(`
    state.lang='fa';
    const event={type:'PLAYER_SPOKE',actor:'P2',text:'استعلام در evt_000053 ثبت شد.'};
    assert.ok(!eventSummary(event).includes('evt_000053'));
    assert.ok(eventSummary(event).includes('رویداد ثبت‌شده'));
    assert.ok(event.text.includes('evt_000053'));
  `);
});

function harness(storage = new Map()) {
  const nodes = new Map();
  const element = (selector) => {
    if (!nodes.has(selector)) nodes.set(selector, {
      innerHTML: '', textContent: '', value: '', disabled: false, dataset: {}, handlers: {}, options: [], dispatchEvent(){},
      classList: { add(){}, remove(){}, toggle(){}, contains(){ return false; } },
      addEventListener(name, fn) { this.handlers[name] = fn; },
      setAttribute(){}, removeAttribute(){}, focus(){},
      querySelectorAll(){ return []; },
    });
    return nodes.get(selector);
  };
  const claim = element('claim'); claim.dataset.claim = 'CITIZEN';
  const context = vm.createContext({ AbortController, Event,
    assert, console, setTimeout, clearTimeout,
    localStorage: {
      getItem: key => storage.get(key) ?? null,
      setItem: (key, value) => storage.set(key, value),
      removeItem: key => storage.delete(key),
    },
    document: {
      documentElement: {}, querySelector: element,
      querySelectorAll: selector => selector === '[data-claim]' ? [claim] : [],
    },
    window: { setTimeout(){}, clearTimeout(){}, setInterval(){}, clearInterval(){}, matchMedia(){return {matches:true};} },
    requestAnimationFrame: fn => fn(),
    EventSource: class { addEventListener(){} close(){} },
    claim,
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../Frontend/journal.js'), 'utf8'), context);
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../Frontend/archive.js'), 'utf8'), context);
  vm.runInContext(source.slice(0, bootstrap), context);
  vm.runInContext(`
    state.gameId = 'test_game'; state.token = 'human-secret'; state.characterId = 1;
    state.characterMap = buildCharacterMap(1);
    state.playerNames = {};
    state.private = {role:'CITIZEN', alive:true, trust:{}, investigations:[]};
    state.public = {
      phase:'ROLE_CLAIM', round:1, winner:null, alive_players:['P1','P2','P3','P4','P5','P6','P7'],
      players:Object.fromEntries(Array.from({length:7},(_,i)=>['P'+(i+1),{alive:true,shunned:false}])),
      role_claims:{}, revealed_roles:{}, discussion_order:[],
    };
    state.run = {status:'WAITING_FOR_HUMAN', fallback_actions:0};
    state.availableActions = ['ROLE_CLAIM'];
    let serverPublic = state.public;
    let serverActions = state.availableActions;
    let serverRun = state.run;
    let serverEvents = [];
    function serverResponse(url) {
      return {ok:true, json:async()=> url.endsWith('/run-state') ? serverRun : ({
        public_state:serverPublic, private_state:state.private, available_actions:serverActions,
        events:serverEvents, player_names:{},
      })};
    }
    let fetch = async url => serverResponse(url);
  `, context);
  return { storage, nodes, run: code => vm.runInContext(`(async()=>{${code}})()`, context) };
}

for (const ordering of ['sse-first', 'http-first']) {
  test(`claim advances without another event when ${ordering}`, async () => {
    const h = harness();
    await h.run(`
      fetch = async (url, options) => {
        if (options?.method === 'POST') {
          serverPublic = {...state.public, phase:'DAY_DISCUSSION', role_claims:Object.fromEntries(state.public.alive_players.map(id=>[id,'CITIZEN']))};
          serverActions = ['SPEAK','ASK','PASS'];
          ${ordering === 'sse-first' ? 'await syncState(true);' : ''}
          return {ok:true};
        }
        return serverResponse(url);
      };
      showClaim();
      await claim.handlers.click();
      assert.equal(state.stage, 'claims');
      await syncState(true);
      assert.equal(state.stage, 'claims');
      await $('#claims-next').handlers.click();
      assert.equal(state.stage, 'human_discussion');
    `);
  });
}

test('failed action retains the form and a second attempt can advance', async () => {
  const h = harness();
  await h.run(`
    let attempts = 0;
    fetch = async (url, options) => {
      if (options?.method === 'POST') {
        if (++attempts === 1) throw new Error('network unavailable');
        serverPublic = {...state.public, phase:'DAY_DISCUSSION', role_claims:{P1:'CITIZEN'}};
        serverActions = ['SPEAK'];
        return {ok:true};
      }
      return serverResponse(url);
    };
    showClaim();
    await claim.handlers.click();
    assert.equal(state.stage, 'claim');
    assert.equal(actionInFlight, false);
    await claim.handlers.click();
    assert.equal(state.stage, 'claims');
  `);
});

for (const status of ['FAILED', 'CANCELLED']) {
  test(`${status} shows a terminal message instead of a waiting screen`, async () => {
    const h = harness();
    await h.run(`
      state.stage='play_wait'; state.run.status='${status}';
      state.public.phase='DAY_DISCUSSION';
      routeAfterSync();
      assert.equal(state.stage,'stopped');
      assert.ok($('#story-content').innerHTML.includes(text('${status === 'FAILED' ? 'failedText' : 'cancelledText'}')));
      assert.ok($('#stopped-home').handlers.click);
    `);
  });
}

test('final vote remains visible until acknowledged, even after another sync', async () => {
  const h = harness();
  await h.run(`
    state.stage='vote_wait'; state.voteRound=3; state.narrativeRound=3;
    state.public.phase='GAME_OVER'; state.public.winner='CITIZEN'; state.run.status='COMPLETED';
    state.events=[{event_id:'last-vote',type:'PLAYER_ELIMINATED',reason:'DAY_VOTE',round:3,player:'P2'}];
    routeAfterSync();
    assert.equal(state.stage,'vote_result');
    routeAfterSync();
    assert.equal(state.stage,'vote_result');
    await $('#vote-next').handlers.click();
    assert.equal(state.stage,'game_over');
    assert.ok(state.acknowledgedResults.has('last-vote'));
  `);
});

test('final night shows morning before game over', async () => {
  const h = harness();
  await h.run(`
    state.stage='night_wait'; state.nightRound=3; state.narrativeRound=3;
    state.public.phase='GAME_OVER'; state.public.winner='MAFIA'; state.run.status='COMPLETED';
    state.events=[{event_id:'last-night',type:'NIGHT_RESULT',result:'PLAYER_KILLED',round:3,player:'P2',revealed_role:'CITIZEN'}];
    serverEvents=state.events;
    routeAfterSync();
    assert.equal(state.stage,'morning');
    routeAfterSync();
    assert.equal(state.stage,'morning');
    await $('#morning-next').handlers.click({currentTarget:$('#morning-next')});
    assert.equal(state.stage,'game_over');
    assert.ok(state.acknowledgedResults.has('last-night'));
  `);
});

test('game over does not interrupt a discussion slide being read', async () => {
  const h = harness();
  await h.run(`
    state.narrativeRound=3; state.public.phase='GAME_OVER'; state.public.winner='CITIZEN'; state.run.status='COMPLETED';
    state.events=[
      {event_id:'speech', type:'PLAYER_SPOKE', actor:'P2', round:3, text:'Evidence'},
      {event_id:'vote', type:'PLAYER_ELIMINATED', player:'P2', reason:'DAY_VOTE', round:3},
    ];
    showDiscussionEvent(state.events[0]); routeAfterSync();
    assert.equal(state.stage,'discussion_event');
    await $('#dialogue-next').handlers.click();
    assert.equal(state.stage,'vote_result');
  `);
});

test('refresh restores credentials and the voting screen from the server', async () => {
  const first = harness();
  await first.run(`state.stage='vote'; state.narrativeRound=2; state.voteRound=2; state.lang='de'; saveSession();`);
  const restored = harness(first.storage);
  await restored.run(`
    serverPublic={...state.public, phase:'DAY_VOTING', round:2}; serverActions=['SUBMIT_VOTE_DECISION'];
    let privateReads=0;
    fetch=async(url,options)=>{
      if (url.endsWith('/observation')) {
        assert.equal(options.headers['X-Player-Token'],'human-secret'); privateReads++;
      }
      return serverResponse(url);
    };
    await restoreSession();
    assert.equal(privateReads,1); assert.equal(state.lang,'de');
    assert.equal(state.stage,'vote'); assert.equal(state.voteRound,2);
    assert.equal(state.gameId,'test_game');
  `);
});

test('refresh restores an unacknowledged final result instead of skipping it', async () => {
  const first = harness();
  await first.run(`state.stage='vote_result'; state.voteRound=3; state.narrativeRound=3; state.currentResultId='final'; saveSession();`);
  const restored = harness(first.storage);
  await restored.run(`
    serverPublic={...state.public, phase:'GAME_OVER', round:3, winner:'CITIZEN'};
    serverRun={status:'COMPLETED'}; serverActions=[];
    serverEvents=[{event_id:'final',type:'PLAYER_ELIMINATED',reason:'DAY_VOTE',round:3,player:'P2'}];
    await restoreSession(); assert.equal(state.stage,'vote_result');
    await $('#vote-next').handlers.click(); assert.equal(state.stage,'game_over');
  `);
});

test('refresh during an unsent vote restores voting instead of waiting for a nonexistent result', async () => {
  const first = harness();
  await first.run(`state.stage='vote_wait'; state.voteRound=2; state.narrativeRound=2; saveSession();`);
  const restored = harness(first.storage);
  await restored.run(`
    serverPublic={...state.public, phase:'DAY_VOTING', round:2};
    serverActions=['SUBMIT_VOTE_DECISION'];
    await restoreSession();
    assert.equal(state.stage,'vote');
  `);
});

test('double-clicking an action sends only one request', async () => {
  const h = harness();
  await h.run(`
    let release, calls=0;
    const pending=new Promise(resolve=>{release=resolve;});
    fetch=async(url,options)=>{
      if(options?.method==='POST') {
        calls++; await pending;
        serverPublic={...state.public, phase:'DAY_DISCUSSION', role_claims:{P1:'CITIZEN'}};
        serverActions=['SPEAK'];
        return {ok:true};
      }
      return serverResponse(url);
    };
    showClaim();
    const first=claim.handlers.click();
    await claim.handlers.click();
    assert.equal(calls,1);
    release(); await first;
    assert.equal(state.stage,'claims');
  `);
});

test('expired sessions are cleared, temporary connection failures remain retryable', async () => {
  const first = harness();
  await first.run(`state.stage='vote'; saveSession();`);
  const restored = harness(first.storage);
  await restored.run(`
    fetch=async()=>{throw new Error('offline');};
    await restoreSession();
    assert.equal(state.stage,'connection_error'); assert.ok(readStored(SESSION_KEY,null));
    fetch=async()=>({ok:false,status:404});
    await restoreSession();
    assert.equal(state.stage,'home'); assert.equal(readStored(SESSION_KEY,null),null);
  `);
});

test('wrong online access code is distinguished from a network failure', async () => {
  await harness().run(`
    state.lang='fa';
    assert.equal(text('accessDenied'),'کد دسترسی بازی آنلاین نادرست است.');
  `);
});

test('journal ignores obsolete filters, preserves all public rounds and excludes private events', async () => {
  await harness().run(`
    const base={visibility:'PUBLIC',round:1};
    state.events=[{...base,type:'VOTE_CAST',actor:'P1',target:'P3'},
      {...base,type:'VOTE_CAST',actor:'P2',target:'P3'},
      {...base,type:'PLAYER_SPOKE',actor:'P2',text:'needle'},
      {...base,round:2,type:'PLAYER_SPOKE',actor:'P2',text:'different'},
      {...base,round:3,visibility:'PRIVATE',type:'PLAYER_SPOKE',actor:'P2',text:'needle'}];
    state.journalFilters={query:'',round:'',player:'P1',kind:'votes'};
    let html=renderJournal();
    assert.equal((html.match(/<tr>/g)||[]).length,3);
    assert.ok(html.includes('needle'));
    state.journalFilters={round:'1',player:'',kind:''};
    html=renderJournal();
    assert.ok(html.includes('round-1'));
    assert.ok(html.includes('round-2') && !html.includes('round-3'));
    assert.ok(!renderTimeline().includes('journal-filters'));
    assert.ok(!renderTimeline().includes('data-journal-filter'));
  `);
});

test('completed reports survive reload, omit credentials and open offline without actions', async () => {
  const first=harness();
  await first.run(`
    saveCompletedReport(); assert.equal(completedReports().length,0);
    state.public.phase='GAME_OVER'; state.public.winner='CITIZEN';
    state.observationUrl='/secret-url'; state.run.control_token='control-secret';
    saveCompletedReport(); saveCompletedReport();
    assert.equal(completedReports().length,1);
    const raw=localStorage.getItem(COMPLETED_REPORTS_KEY);
    for(const secret of ['human-secret','secret-url','control-secret']) assert.ok(!raw.includes(secret));
  `);
  await harness(first.storage).run(`
    let calls=0; fetch=async()=>{calls++; throw new Error('offline');};
    openCompletedReport(completedReports()[0]);
    assert.equal(state.stage,'game_over'); assert.equal(state.token,null);
    assert.equal(state.availableActions.length,0); assert.equal(state.archiveMode,true);
    saveSession(); assert.equal(readStored(SESSION_KEY,null),null);
    await syncState(); await goHome(); assert.equal(calls,0);
    assert.equal(completedReports().length,1);
  `);
});

test('archive handles invalid storage and storage quota failures', async () => {
  await harness().run(`
    localStorage.setItem(COMPLETED_REPORTS_KEY,JSON.stringify([null,{}, {version:1,gameId:'bad'}]));
    assert.equal(completedReports().length,0);
    state.public.phase='GAME_OVER';
    localStorage.setItem=()=>{throw new Error('quota exceeded');};
    saveCompletedReport(); assert.equal(state.archiveSaveFailed,true);
    assert.equal(state.public.phase,'GAME_OVER');
  `);
});

test('late network responses cannot overwrite an opened archive of the same game', async () => {
  await harness().run(`
    state.public={...state.public,phase:'GAME_OVER'}; saveCompletedReport();
    let release;
    const gate=new Promise(resolve=>{release=resolve;});
    fetch=async url=>{await gate; return serverResponse(url);};
    const pending=syncState();
    openCompletedReport(completedReports()[0]);
    release(); await pending;
    assert.equal(state.public.phase,'GAME_OVER');
    assert.equal(state.stage,'game_over'); assert.equal(state.availableActions.length,0);
  `);
});

test('declared position and vote explanation are visible with escaped text', async()=>{
  await harness().run(`
    state.lang='fa';
    const event={type:'PLAYER_SPOKE',actor:'P3',text:'گفتهٔ کوتاه',position:{target:'P4',reason:'شاهد تازه'}};
    assert.ok(eventDialogue(event).includes('Marco Conti'));
    assert.ok(eventSummary(event).includes('مظنون اعلام‌شده'));
    const html=journalVotes([{type:'VOTE_CAST',actor:'P3',target:'P4',round:2,position:{reason:'<script>bad</script>'}}],2);
    assert.ok(!html.includes('<script>') && html.includes('&lt;script&gt;'));
  `);
});

test('postgame night review opens the existing journal and keeps missing old causes explicit', async()=>{
  await harness().run(`
    state.lang='fa'; state.public.phase='GAME_OVER';
    showGameOver();
    assert.ok($('#story-content').innerHTML.includes('review-nights'));
    $('#review-nights').handlers.click();
    assert.equal(state.consoleTab,'timeline'); assert.equal(state.journalFilters.kind,'');
    state.nightReplay=[];
    const html=journalNight([{type:'NIGHT_RESULT',result:'PLAYER_KILLED',player:'P2',round:2}],2);
    assert.ok(html.includes('نسخهٔ قدیمی'));
  `);
});
