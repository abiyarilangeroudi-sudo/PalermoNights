from __future__ import annotations

import asyncio
import json
import time
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.ai.runner import RunnerEntry
from app.ai.service import AIRun, update_run_progress, build_runner
from app.domain import Investigation, Phase, PlayerType, Role
from app.engine import GameEngine
from app.main import ai_runs, app, games


def settled(client, created):
    for _ in range(200):
        state = client.get(created["run_state_url"], headers={"X-Player-Token": created["human"]["token"]} if "human" in created else {}).json()
        if state["status"] not in {"QUEUED", "RUNNING"}:
            return state
        time.sleep(0.005)
    raise AssertionError("run did not settle")


def create_interactive(client):
    response = client.post("/games/interactive", json={"character_id": 1, "ai_mode": "offline"})
    assert response.status_code == 202
    created = response.json()
    settled(client, created)
    return created, {"X-Player-Token": created["human"]["token"]}


@pytest.mark.parametrize("path,payload", [
    ("/games", {}), ("/games/ai", {"mode": "offline"}),
    ("/games/interactive", {"character_id": 1, "ai_mode": "offline"}),
])
def test_http_creation_rejects_client_seed(path, payload):
    with TestClient(app) as client:
        assert client.post(path, json={**payload, "seed": 12}).status_code == 422


def test_public_progress_never_contains_role_specific_actions_or_diagnostics():
    run = AIRun(game_id="privacy_probe", mode="offline", human_player_id="P1", human_token="human-secret")
    with patch("app.ai.service._write_audit_record"):
        for action in ["SELECT_STRATEGY", "PROTECT", "INVESTIGATE", "KILL"]:
            update_run_progress(run, RunnerEntry(1, 1, "NIGHT_ACTION", "P3", action, "fallback", "private diagnostic"))
            run.awaiting_actions = [action]
            run.summary = {"actions": 15, "failures": [{"player_id": "P3", "action": action}],
                           "fallback_actions_by_type": {action: 1}}
            public = json.dumps(run.public_dict())
            for secret in [action, "P3", "private diagnostic", "human-secret", run.control_token]:
                assert secret not in public


def test_interactive_run_state_and_sse_do_not_leak_boss(seeded_api_game):
    seeded_api_game(12)
    with TestClient(app) as client:
        created, headers = create_interactive(client)
        run = ai_runs.get(created["game_id"])
        assert run.last_action["action"] == "SELECT_STRATEGY"
        assert run.last_action["player_id"] == "P3"
        public = client.get(created["run_state_url"]).json()
        assert "last_action" not in public and "awaiting_actions" not in public
        observation = client.get(created["observation_url"], headers=headers).json()
        assert observation["available_actions"] == ["ROLE_CLAIM"]
        client.post(f"/game/{created['game_id']}/run/cancel", headers=headers)
        with client.stream("GET", created["stream_url"]) as response:
            stream = "".join(response.iter_text())
        assert "SELECT_STRATEGY" not in stream and "control_token" not in stream


def test_public_wait_status_does_not_identify_a_human_boss(seeded_api_game):
    seeded_api_game(3)
    with TestClient(app) as client:
        created, headers = create_interactive(client)
        url = created["run_state_url"]
        assert ai_runs.get(created["game_id"]).awaiting_actions == ["SELECT_STRATEGY"]
        assert client.get(url).json()["status"] == "RUNNING"
        assert client.get(url, headers=headers).json()["status"] == "WAITING_FOR_HUMAN"
        assert client.get(url, headers={"X-Player-Token": "wrong"}).status_code == 401


def test_generic_action_cannot_desynchronize_interactive_runner(seeded_api_game):
    seeded_api_game(12)
    with TestClient(app) as client:
        created, headers = create_interactive(client)
        game_id = created["game_id"]
        payload = {"action": "ROLE_CLAIM", "claimed_role": "CITIZEN"}
        rejected = client.post(f"/game/{game_id}/player/P1/action", headers=headers, json=payload)
        assert rejected.status_code == 409
        assert rejected.json()["error"] == "USE_INTERACTIVE_ACTION_ENDPOINT"
        assert games.get(game_id).players["P1"].role_claim is None
        assert client.post(f"/game/{game_id}/interactive/action", headers=headers, json=payload).status_code == 200
        settled(client, created)
        assert all(player.role_claim for player in games.get(game_id).players.values())


def test_cancel_requires_human_token_and_other_game_token_is_rejected(seeded_api_game):
    seeded_api_game(12)
    with TestClient(app) as client:
        created, headers = create_interactive(client)
        other, other_headers = create_interactive(client)
        path = f"/game/{created['game_id']}/run/cancel"
        for invalid in [{}, {"X-Player-Token": "wrong"}, other_headers]:
            assert client.post(path, headers=invalid).status_code == 401
            assert ai_runs.get(created["game_id"]).status == "WAITING_FOR_HUMAN"
        result = client.post(path, headers=headers)
        assert result.status_code == 200 and result.json()["status"] == "CANCELLED"
        assert ai_runs.get(created["game_id"]).finished_at


def test_ai_only_cancel_requires_separate_control_token():
    async def paused_run(run, runner):
        run.status = "RUNNING"
        await asyncio.Event().wait()

    with patch("app.main.execute_run", paused_run), TestClient(app) as client:
        created = client.post("/games/ai", json={"mode": "offline"}).json()
        path = f"/game/{created['game_id']}/run/cancel"
        assert client.post(path).status_code == 401
        assert client.post(path, headers={"X-Run-Token": "wrong"}).status_code == 401
        assert client.post(path, headers={"X-Run-Token": created["control_token"]}).status_code == 200
        assert created["control_token"] not in json.dumps(client.get(created["run_state_url"]).json())


@pytest.mark.anyio
async def test_fallback_detective_prefers_unknown_legal_targets_and_handles_exhaustion():
    engine = GameEngine()
    game = engine.create_game([PlayerType.AI] * 7, fixed_roles=[
        Role.CITIZEN, Role.MAFIA_BOSS, Role.MAFIA_DEPUTY,
        Role.DOCTOR, Role.DETECTIVE, Role.CITIZEN, Role.CITIZEN,
    ])
    game.phase = Phase.NIGHT_ACTION
    game.players["P5"].investigations = [Investigation(1, "P1", Role.CITIZEN)]
    game.players["P2"].shunned = True
    game.players["P6"].alive = False
    runner = build_runner(engine, game, mode="offline", settings=None, live_action_budget=None)
    agent = runner.agents["P5"]
    decision = await agent.decide(runner.observation("P5"))
    assert decision.payload["target"] in {"P3", "P4", "P7"}
    for pid in ["P3", "P4", "P7"]:
        game.players["P5"].investigations.append(Investigation(2, pid, game.players[pid].role))
    decision = await agent.decide(runner.observation("P5"))
    assert decision.payload["target"] in {"P1", "P3", "P4", "P7"}
    engine.submit_action(game, "P5", decision.action, decision.payload)
