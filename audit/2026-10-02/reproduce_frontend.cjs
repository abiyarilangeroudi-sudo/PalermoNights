// Unit-level reproduction of the actual frontend routing functions, with a
// minimal DOM and controlled network/event ordering. No browser/network access.
// Run: node audit/2026-10-02/reproduce_frontend.cjs
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../../Frontend/app.js'), 'utf8');
const bootstrap = source.lastIndexOf('$("#new-game").addEventListener');
assert(bootstrap > 0);
const elements = new Map();
function element(selector) {
  if (!elements.has(selector)) elements.set(selector, {
    dataset: {}, handlers: {}, disabled: false, value: '', textContent: '',
    innerHTML: '', classList: {add(){}, remove(){}, toggle(){}},
    addEventListener(name, fn) { this.handlers[name] = fn; },
    setAttribute(){}, removeAttribute(){}, focus(){},
  });
  return elements.get(selector);
}
const claim = element('claim');
claim.dataset.claim = 'CITIZEN';
const context = vm.createContext({
  console, assert,
  document: {querySelector: element, querySelectorAll: s => s === '[data-claim]' ? [claim] : []},
  window: {setTimeout(){}, clearTimeout(){}, setInterval(){}, clearInterval(){}},
  requestAnimationFrame(){},
  claim,
});
vm.runInContext(source.slice(0, bootstrap), context);
vm.runInContext(`
(async () => {
  const output = (probe, data) => console.log(JSON.stringify({probe, ...data}));
  // Render functions are replaced only to avoid needing a layout engine.
  renderStory = () => {};
  state.gameId = 'audit';
  state.characterMap = buildCharacterMap(1);
  state.private = {role: 'CITIZEN', alive: true};
  state.public = {phase: 'ROLE_CLAIM', round: 1, players: {}, role_claims: {}};
  state.run = {status: 'WAITING_FOR_HUMAN'};
  state.availableActions = ['ROLE_CLAIM'];
  // A valid ordering: SSE updates finish before the POST response; the POST
  // then refreshes state with route=false. No further server changes occur.
  submitHumanAction = async () => {
    state.public.phase = 'DAY_DISCUSSION';
    state.public.role_claims = Object.fromEntries(Array.from({length:7}, (_,i)=>['P'+(i+1),'CITIZEN']));
    state.availableActions = ['SPEAK','ASK','PASS'];
    routeAfterSync();
  };
  showClaim();
  await claim.handlers.click();
  assert.equal(state.stage, 'wait_claims');
  assert.equal(state.public.phase, 'DAY_DISCUSSION');
  output('post_sse_ordering_stalls', {stage: state.stage, phase: state.public.phase, available: state.availableActions});

  state.stage = 'play_wait';
  state.public.phase = 'DAY_DISCUSSION';
  state.run.status = 'FAILED';
  state.run.error = 'RunnerLimitExceeded';
  state.events = [];
  state.availableActions = [];
  routeAfterSync();
  assert.equal(state.stage, 'play_wait');
  output('failed_run_stays_waiting', {stage: state.stage, status: state.run.status});

  state.stage = 'vote_wait';
  state.voteRound = 3;
  state.public.phase = 'GAME_OVER';
  state.public.winner = 'CITIZEN';
  state.run.status = 'COMPLETED';
  state.events = [{type:'PLAYER_ELIMINATED', round:3, player:'P2', reason:'DAY_VOTE'}];
  routeAfterSync();
  assert.equal(state.stage, 'game_over');
  output('final_vote_result_skipped', {stage: state.stage, pending: state.events[0].type});
})().catch(error => { console.error(error); throw error; });
`, context);
