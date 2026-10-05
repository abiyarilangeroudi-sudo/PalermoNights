from __future__ import annotations

import asyncio
import copy
import time
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.main import app, ai_runs, games, runtime
from app.ai import service
from app.persistence import SnapshotStore, game_from_dict, snapshot


def create(client):
    response = client.post('/games/interactive', json={'character_id': 1, 'ai_mode': 'offline'})
    assert response.status_code == 202, response.text
    body = response.json()
    headers = {'X-Player-Token': body['human']['token']}
    for _ in range(300):
        state = client.get(body['run_state_url'], headers=headers).json()
        if state['status'] == 'WAITING_FOR_HUMAN':
            return body, headers
        time.sleep(.01)
    raise AssertionError(state)


def action_payload(run):
    if run.awaiting_actions == ['SELECT_STRATEGY']:
        return {'action': 'SELECT_STRATEGY', 'strategy': 'USE_CONTRADICTION'}
    return {'action': 'ROLE_CLAIM', 'claimed_role': 'CITIZEN'}


def test_audit_failure_does_not_break_action_and_receipt_survives_restart(monkeypatch, seeded_api_game):
    seeded_api_game(12)
    monkeypatch.setattr(service, '_write_audit_record', lambda *args: (_ for _ in ()).throw(OSError('disk full')))
    with TestClient(app) as client:
        body, headers = create(client)
        run = ai_runs.get(body['game_id'])
        payload = {**action_payload(run), 'request_id': 'stable-request-1'}
        url = f"/game/{run.game_id}/interactive/action"
        first = client.post(url, json=payload, headers=headers)
        assert first.status_code == 200
        replay = client.post(url, json=payload, headers=headers)
        assert replay.json() == first.json()
        assert sum(e.action == payload['action'] and e.player_id == 'P1' for e in run.runner.transcript) == 1
    # Fresh in-memory repositories model a new application process.
    games._games.clear(); ai_runs._runs.clear()
    with TestClient(app) as client:
        run = ai_runs.get(body['game_id'])
        replay = client.post(url, json=payload, headers=headers)
        assert replay.status_code == 200 and replay.json() == first.json()
        assert sum(e.action == payload['action'] and e.player_id == 'P1' for e in run.runner.transcript) == 1
        assert client.get(body['observation_url'], headers=headers).status_code == 200
        conflict = client.post(url, json={**payload, 'claimed_role': 'DOCTOR'}, headers=headers)
        assert conflict.status_code == 409
        assert 'accepted_request_ids' not in client.get(body['run_state_url']).json()


def test_failed_durable_commit_rolls_back_action_and_allows_same_retry(monkeypatch):
    with TestClient(app, raise_server_exceptions=False) as client:
        body, headers = create(client)
        run = ai_runs.get(body['game_id'])
        before = copy.deepcopy(snapshot(games.get(run.game_id), run))
        payload = {**action_payload(run), 'request_id': 'disk-retry-action'}
        url = f'/game/{run.game_id}/interactive/action'
        real_save = runtime.store.save
        with monkeypatch.context() as patch:
            patch.setattr(runtime.store, 'save', lambda *args: (_ for _ in ()).throw(OSError('disk full')))
            response = client.post(url, json=payload, headers=headers)
        assert response.status_code == 500
        assert snapshot(games.get(run.game_id), run) == before
        assert client.post(url, json=payload, headers=headers).status_code == 200


def test_stale_action_is_rejected_without_mutating_game():
    with TestClient(app) as client:
        body, headers = create(client)
        run = ai_runs.get(body['game_id'])
        before = snapshot(games.get(run.game_id), run)
        response = client.post(f'/game/{run.game_id}/interactive/action', headers=headers,
            json={**action_payload(run), 'request_id': 'stale-action-123', 'expected_event_id': 'old-event'})
        assert response.status_code == 409
        assert snapshot(games.get(run.game_id), run) == before


def test_restore_preserves_agent_memory_budget_and_private_night_state():
    from app.ai.agent import AgentMemory
    with TestClient(app) as client:
        body, headers = create(client)
        run = ai_runs.get(body['game_id'])
        agent = run.runner.agents['P2']
        agent.state.memory = [AgentMemory('e-test', 'remember a claim', 2, .8)]
        agent.state.beliefs = {'P3': .83}
        agent.state.seen_event_ids = {'e-test'}
        agent.remote_decisions_used = 7
        agent.gate_decisions_used = 3
        game = games.get(run.game_id)
        game.night_actions = {'KILL': 'P3', 'PROTECT': 'P4'}
        game.players['P2'].previous_protection_target = 'P3'
        expected = copy.deepcopy(snapshot(game, run))
        runtime.save(game.game_id)
    games._games.clear(); ai_runs._runs.clear()
    with TestClient(app) as client:
        actual = snapshot(games.get(body['game_id']), ai_runs.get(body['game_id']))
        assert actual == expected
        assert client.get(body['observation_url'], headers=headers).status_code == 200


def test_live_creation_requires_signed_session_and_rejects_before_provider(monkeypatch):
    monkeypatch.setenv('PALERMO_PLAY_KEY', 'test-access-code')
    monkeypatch.delenv('PALERMO_ALLOW_LOCAL_LIVE', raising=False)
    with TestClient(app) as client:
        for path, body in [('/games/ai', {'mode':'live'}), ('/games/interactive', {'character_id':1})]:
            assert client.post(path, json=body).status_code == 401
        assert not ai_runs._runs
        assert client.post('/session', headers={'X-Play-Key':'wrong'}).status_code == 401
        response = client.post('/session', headers={'X-Play-Key':'test-access-code'})
        assert response.status_code == 200
        assert 'HttpOnly' in response.headers['set-cookie']
        monkeypatch.setenv('PALERMO_LIVE_GAMES_PER_DAY', '1')
        runtime.store.record_admission(('another-client', 1, time.time()))
        assert client.post('/games/ai', json={'mode':'live'}).status_code == 429
        assert not ai_runs._runs


def test_creation_limits_survive_restart_and_cannot_be_bypassed_with_header(monkeypatch):
    monkeypatch.setenv('PALERMO_GAMES_PER_HOUR', '1')
    with TestClient(app) as client:
        client.post('/games', json={})
        response = client.post('/games', json={}, headers={'X-Forwarded-For':'1.2.3.4'})
        assert response.status_code == 429 and response.headers['retry-after']
    games._games.clear(); ai_runs._runs.clear()
    with TestClient(app) as client:
        assert client.post('/games', json={}).status_code == 429


def test_concurrent_game_limit_and_cross_origin(monkeypatch):
    monkeypatch.setenv('PALERMO_MAX_ACTIVE_PER_CLIENT', '1')
    with TestClient(app) as client:
        create(client)
        assert client.post('/games/interactive', json={'character_id':1,'ai_mode':'offline'}).status_code == 429
        assert client.post('/games', json={}, headers={'Origin':'https://other.example'}).status_code == 403


def test_worker_creation_requires_access_for_live_games(monkeypatch):
    with TestClient(app) as client:
        monkeypatch.setenv('PALERMO_CLOUDFLARE_WORKER', '1')
        assert client.post('/games/ai', json={'mode':'live'}).status_code == 401
        assert client.post('/games', json={}).status_code == 201


def test_only_one_process_can_own_store(tmp_path):
    path = str(tmp_path / 'exclusive.sqlite3')
    first, second = SnapshotStore(path), SnapshotStore(path)
    first.open()
    try:
        with pytest.raises(RuntimeError, match='one application worker'):
            second.open()
    finally:
        first.close()
    second.open(); second.close()


@pytest.mark.anyio
async def test_expired_waiting_games_release_capacity():
    from app.ai.service import AIRun
    from app.domain import PlayerType
    from app.main import engine
    game = engine.create_game([PlayerType.AI] * 7)
    games.add(game)
    run = AIRun(game_id=game.game_id, mode='offline', status='WAITING_FOR_HUMAN',
        created_at=(datetime.now(UTC)-timedelta(days=2)).isoformat())
    ai_runs.add(run)
    await runtime.expire()
    assert run.status == 'CANCELLED'


@pytest.mark.anyio
async def test_budget_reserved_before_model_request_and_enforced_after_restore():
    from app.ai.agent import AIAgent, Observation
    from app.ai.providers import ProviderError
    from app.main import engine
    from app.domain import PlayerType
    from app.ai.runner import HeadlessGameRunner
    game = engine.create_game([PlayerType.AI]*7, seed=12)
    provider = AsyncMock()
    provider.generate_json.side_effect = ProviderError('temporary')
    agent = AIAgent('P1', provider, remote_decision_budget=1)
    from app.ai.agent import AgentDecision
    agent.fallback_decision = lambda _: AgentDecision('ROLE_CLAIM', {'claimed_role':'CITIZEN'}, 'fallback')
    agent._gate_target = AsyncMock(side_effect=lambda value, _: value)
    observation = HeadlessGameRunner(engine, game, {}).observation('P1', ['ROLE_CLAIM'])
    reservations = []
    agent.checkpoint = lambda: reservations.append(agent.remote_decisions_used)
    await agent.decide(observation)
    await agent.decide(observation)
    assert reservations == [1]
    assert provider.generate_json.await_count == 1


def test_snapshot_recovers_in_a_separate_python_process():
    import hashlib
    import json
    import subprocess
    import sys
    with TestClient(app) as client:
        body, _ = create(client)
        expected = snapshot(games.get(body['game_id']), ai_runs.get(body['game_id']))
    digest = hashlib.sha256(json.dumps(expected, sort_keys=True).encode()).hexdigest()
    script = """
import hashlib, json
from fastapi.testclient import TestClient
from app.main import app, games, ai_runs
from app.persistence import snapshot
with TestClient(app):
    gid = next(iter(games._games))
    value = snapshot(games.get(gid), ai_runs.get(gid))
    print(hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest())
"""
    child = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True, timeout=15, check=True)
    assert child.stdout.strip() == digest


@pytest.mark.anyio
async def test_inflight_decision_is_reserved_and_resumes_after_shutdown():
    from app.ai.service import AIRun, build_runner
    from app.domain import PlayerType
    from app.main import engine
    from app.runtime import GameRuntime
    from app.repository import InMemoryGameRepository
    from app.ai.service import AIRunRegistry
    local = GameRuntime(engine, InMemoryGameRepository(), AIRunRegistry())
    store = SnapshotStore(':memory:'); store.open(); local.store = store
    try:
        game = engine.create_game([PlayerType.HUMAN, *([PlayerType.AI]*6)], seed=12)
        local.games.add(game)
        run = AIRun(game_id=game.game_id, mode='offline', human_player_id='P1')
        local.runs.add(run)
        runner = build_runner(engine, game, mode='offline', settings=None, live_action_budget=2)
        started = asyncio.Event()
        async def pending(**kwargs):
            started.set()
            await asyncio.Event().wait()
        for agent in runner.agents.values():
            agent.provider.generate_json = pending
        local.start(run, runner)
        await asyncio.wait_for(started.wait(), 2)
        reserved = sum(a.remote_decisions_used for a in runner.agents.values())
        assert reserved == 1
        await local.stop()
        saved = store.all()[0]
        assert saved['run']['status'] == 'QUEUED'
        assert sum(a['remote_used'] for a in saved['agents'].values()) == 1
        local.games._games.clear(); local.runs._runs.clear()
        local.restore(saved)
        restored = local.runs.get(game.game_id)
        await asyncio.wait_for(restored.task, 2)
        assert restored.status == 'WAITING_FOR_HUMAN'
        assert len(restored.runner.transcript) == 1
        assert sum(a.remote_decisions_used for a in restored.runner.agents.values()) == 2
    finally:
        await local.stop()
        store.close()


def test_failed_cancel_cannot_be_mistaken_for_a_durable_terminal_state(monkeypatch):
    with TestClient(app, raise_server_exceptions=False) as client:
        body, headers = create(client)
        url = f"/game/{body['game_id']}/run/cancel"
        with monkeypatch.context() as patch:
            patch.setattr(runtime.store, 'save', lambda *args: (_ for _ in ()).throw(OSError('disk full')))
            assert client.post(url, headers=headers).status_code == 500
            assert client.post(url, headers=headers).status_code == 500
        assert client.post(url, headers=headers).status_code == 200
        assert next(v for v in runtime.store.all() if v['game']['game_id'] == body['game_id'])['run']['status'] == 'CANCELLED'


def test_authenticated_live_creation_has_finite_budget_even_when_zero_requested(monkeypatch):
    from app.ai.config import AISettings, ProviderConfig
    import app.runtime as runtime_module
    monkeypatch.setenv('PALERMO_PLAY_KEY', 'test-code')
    monkeypatch.delenv('PALERMO_ALLOW_LOCAL_LIVE', raising=False)
    settings = AISettings(provider_mode='test',
        player_providers=tuple(ProviderConfig('openai', 'test-model', 'fake-key') for _ in range(7)),
        fallback_providers=(), analyst=None, typesafe=None,
        max_output_tokens=9000, speak_max_output_tokens=9000)
    monkeypatch.setattr(AISettings, 'from_environment', lambda **kwargs: settings)
    async def paused(run, runner):
        run.status = 'RUNNING'
        await asyncio.Event().wait()
    monkeypatch.setattr(runtime_module, 'execute_run', paused)
    with TestClient(app) as client:
        assert client.post('/session', headers={'X-Play-Key':'test-code'}).status_code == 200
        response = client.post('/games/ai', json={'mode':'live', 'live_action_budget':0})
        assert response.status_code == 202
        run = ai_runs.get(response.json()['game_id'])
        for agent in run.runner.agents.values():
            assert agent.remote_decision_budget == 20
            assert agent.gate_decision_budget == 20
            assert agent.max_output_tokens == 4096
            assert agent.speak_max_output_tokens == 4096
            assert agent.remote_decisions_used == 0  # No paid network calls in this test.
