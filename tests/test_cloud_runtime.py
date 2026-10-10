"""Exercise the production SQL adapter and bounded turns across a fresh runtime."""
import sqlite3
import json
import pytest
from app.cloud_store import CloudStore
from app.runtime import GameRuntime
from app.repository import InMemoryGameRepository
from app.ai.service import AIRun, AIRunRegistry, build_runner, execute_run
from app.engine import GameEngine
from app.domain import PlayerType, Phase, Role, RuleViolation
from app.ai.library import analyze_game, resources

class Cursor:
    def __init__(self, cursor): self.cursor = cursor
    def raw(self): return self.cursor.fetchall()

class SQL:
    def __init__(self): self.connection = sqlite3.connect(':memory:', isolation_level=None)
    def exec(self, statement, *params): return Cursor(self.connection.execute(statement, params))


def make_runtime(store):
    runtime = GameRuntime(GameEngine(), InMemoryGameRepository(), AIRunRegistry())
    runtime.external_scheduler = True
    runtime.store = store
    return runtime


@pytest.mark.anyio
async def test_cloud_sql_restores_reserved_budgets_and_completes_bounded_turns():
    sql = SQL(); store = CloudStore(sql); runtime = make_runtime(store)
    game = runtime.engine.create_game([PlayerType.AI]*7, seed=12)
    runtime.games.add(game)
    run = AIRun(game.game_id, 'offline'); runtime.runs.add(run)
    runner = build_runner(runtime.engine, game, mode='offline', settings=None, live_action_budget=0)
    runtime.start(run, runner)
    assert run.task is None
    for _ in range(4): await execute_run(run, runner, batch_steps=1)
    used = {pid:a.remote_decisions_used for pid,a in runner.agents.items()}
    saved = store.all()[0]
    runtime = make_runtime(CloudStore(sql)); runtime.restore(saved)
    restored = runtime.runs.get(game.game_id)
    assert {pid:a.remote_decisions_used for pid,a in restored.runner.agents.items()} == used
    for _ in range(300):
        if restored.status == 'COMPLETED': break
        await execute_run(restored, restored.runner, batch_steps=1)
    assert restored.status == 'COMPLETED'
    assert len({e.event_id for e in restored.runner.game.events}) == len(restored.runner.game.events)
    assert store.lessons()[0]['complete']
    assert store.lessons()[0]['status'] == 'candidate'
    assert store.all()[0]['run']['status'] == 'COMPLETED'


def test_cloud_audits_and_admissions_persist_without_files():
    store = CloudStore(SQL())
    store.record_admission(('owner', 1, 1000))
    assert store.admissions_since(0) == [['owner', 1, 1000.0]]
    store.audit('g', {'type':'RUN_FAILED','error':'TimeoutError'})
    assert 'TimeoutError' in store.rows('SELECT body FROM audit')[0][0]


@pytest.mark.parametrize('role', list(Role))
def test_vote_only_is_legal_for_every_role_and_mafia_optional_fields_are_ignored(role):
    engine = GameEngine(); game = engine.create_game([PlayerType.HUMAN]*7, seed=12)
    pid = next(p.player_id for p in game.players.values() if p.role == role)
    target = next(p for p in game.players if p != pid)
    game.phase = Phase.DAY_VOTING
    engine.submit_action(game, pid, 'SUBMIT_VOTE_DECISION', {'vote_target':target})
    assert game.vote_decisions[pid].trusted_player is None
    if game.players[pid].faction == 'MAFIA':
        game.vote_decisions.clear()
        engine.submit_action(game, pid, 'SUBMIT_VOTE_DECISION', {'vote_target':target,'trusted_player':target,'suspect_2':'missing'})
        assert game.vote_decisions[pid].trusted_player is None
        assert game.vote_decisions[pid].suspect_2 is None


def test_citizen_optional_selections_reject_duplicates_and_dead_targets():
    engine=GameEngine();game=engine.create_game([PlayerType.HUMAN]*7,seed=12)
    pid=next(p.player_id for p in game.players.values() if p.role==Role.CITIZEN)
    target, other=[p for p in game.players if p!=pid][:2];game.phase=Phase.DAY_VOTING
    for extras in [{'trusted_player':target},{'suspect_2':target},{'suspect_2':other,'trusted_player':other}]:
        with pytest.raises(RuleViolation): engine.submit_action(game,pid,'SUBMIT_VOTE_DECISION',{'vote_target':target,**extras})
    assert not game.vote_decisions


def test_will_is_a_copied_citizen_snapshot_and_not_published_on_shunning():
    engine=GameEngine();game=engine.create_game([PlayerType.HUMAN]*7,seed=12)
    p=next(p for p in game.players.values() if p.role==Role.CITIZEN)
    p.trust['P1']=73
    engine._eliminate(game,p.player_id,'DAY_VOTE')
    will=next(e for e in game.events if e.type=='WILL_REVEALED')
    assert will.visibility=='PUBLIC' and will.payload['trust']['P1']==73
    p.trust['P1']=0
    assert will.payload['trust']['P1']==73


def test_night_will_is_published_only_with_morning_result():
    engine=GameEngine();game=engine.create_game([PlayerType.HUMAN]*7,seed=12)
    game.phase=Phase.NIGHT_ACTION
    boss=next(p for p in game.players.values() if p.role==Role.MAFIA_BOSS)
    victim=next(p for p in game.players.values() if p.role==Role.CITIZEN)
    game.night_actions[boss.player_id]=victim.player_id
    engine._resolve_night(game)
    types=[e.type for e in game.events]
    assert types.index('NIGHT_RESULT') < types.index('WILL_REVEALED')
    will=next(e for e in game.events if e.type=='WILL_REVEALED')
    assert will.payload['player']==victim.player_id and will.payload['trust']==victim.trust


def test_only_reviewed_completed_cases_enter_optional_library(tmp_path):
    from app.lesson_review import reviewed_card
    from app.ai import library
    from app.ai.runner import HeadlessGameRunner
    engine=GameEngine();game=engine.create_game([PlayerType.AI]*7,seed=12)
    with pytest.raises(ValueError): reviewed_card(analyze_game(game),{})
    game.phase=Phase.GAME_OVER
    case=analyze_game(game)
    fields={key:'An explicitly reviewed example.' for key in ['title','observation','hypothesis','counterexample','limitations']}
    result=reviewed_card(case,fields)
    assert result['status']=='reviewed'
    assert result['source_game']==game.game_id
    assert 'observed' not in result and 'decisions' not in result


@pytest.mark.anyio
async def test_worker_alarm_initialization_and_recovery(monkeypatch):
    import importlib.util
    import sys
    from types import SimpleNamespace
    from app.main import runtime, games, ai_runs
    from app.ai import service
    class Storage:
        def __init__(self): self.sql=SQL();self.next_alarm=None
        async def getAlarm(self): return self.next_alarm
        async def setAlarm(self,value): self.next_alarm=value
        async def deleteAlarm(self): self.next_alarm=None
    class Base:
        def __init__(self,ctx,env): self.ctx=ctx;self.env=env
    monkeypatch.setitem(sys.modules,'workers',SimpleNamespace(DurableObject=Base,WorkerEntrypoint=Base,asgi=None))
    monkeypatch.setenv('PALERMO_CLOUDFLARE_WORKER','1')
    monkeypatch.setattr(runtime,'store',None)
    monkeypatch.setattr(runtime,'external_scheduler',False)
    monkeypatch.setattr(service,'_write_audit_record',service._write_audit_record)
    spec=importlib.util.spec_from_file_location('test_worker_entry','worker.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    storage=Storage();ctx=SimpleNamespace(storage=storage);env=SimpleNamespace()
    worker=module.GameServer(ctx,env);await worker.initialize()
    game=runtime.engine.create_game([PlayerType.AI]*7,seed=12);games.add(game)
    run=AIRun(game.game_id,'offline');ai_runs.add(run)
    runner=build_runner(runtime.engine,game,mode='offline',settings=None,live_action_budget=0)
    runtime.start(run,runner);await worker.arm()
    assert storage.next_alarm is not None
    await worker.alarm()
    assert run.current_step==1 and run.status=='QUEUED'
    games._games.clear();ai_runs._runs.clear()
    worker=module.GameServer(ctx,env);await worker.initialize()
    assert ai_runs.get(game.game_id).current_step==1
    for _ in range(300):
        if ai_runs.get(game.game_id).status=='COMPLETED':break
        await worker.alarm()
    assert ai_runs.get(game.game_id).status=='COMPLETED'
    assert storage.next_alarm is None
    participant_game=runtime.engine.create_game([PlayerType.AI]*7,seed=13);games.add(participant_game)
    participant_run=AIRun(participant_game.game_id,'live',credential_mode='participant');ai_runs.add(participant_run)
    participant_runner=build_runner(runtime.engine,participant_game,mode='offline',settings=None,live_action_budget=0)
    runtime.start(participant_run,participant_runner,schedule=False)
    await worker.alarm()
    assert participant_run.status=='QUEUED' and participant_run.current_step==0

@pytest.mark.anyio
async def test_cancelling_cloud_turn_during_provider_wait_does_not_commit_action():
    import asyncio
    runtime=make_runtime(CloudStore(SQL()))
    game=runtime.engine.create_game([PlayerType.AI]*7,seed=12);runtime.games.add(game)
    run=AIRun(game.game_id,'offline');runtime.runs.add(run)
    runner=build_runner(runtime.engine,game,mode='offline',settings=None,live_action_budget=0)
    runtime.start(run,runner)
    entered=asyncio.Event();release=asyncio.Event()
    pid,_=runner._next_actor();original=runner.agents[pid].decide
    async def wait(obs):
        entered.set();await release.wait();return await original(obs)
    runner.agents[pid].decide=wait
    before=len(game.events)
    task=asyncio.create_task(execute_run(run,runner,batch_steps=1))
    await entered.wait();run.status='CANCELLED';release.set();await task
    assert run.status=='CANCELLED' and len(game.events)==before
    assert runtime.store.all()[0]['run']['status']=='CANCELLED'
