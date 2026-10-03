"""Offline audit probes. Run from the repository root with PYTHONPATH=. .venv/bin/python audit/2026-10-02/reproduce_backend.py.

Assertions confirm the observed bugs in the audited snapshot, not desired behavior.
No provider requests, credentials, or persistent game audit writes are used.
"""
import asyncio
import json
import random
import time
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.ai.agent import AIAgent
from app.ai.service import OfflineProvider, build_runner
from app.domain import Phase, PlayerType, Role
from app.engine import GameEngine, ROLES
from app.main import ai_runs, app, games


def emit(name, **data):
    print(json.dumps({"probe": name, **data}, ensure_ascii=False))


def wait(client, path):
    for _ in range(100):
        state = client.get(path).json()
        if state["status"] not in {"QUEUED", "RUNNING"}:
            return state
        time.sleep(0.005)
    raise AssertionError("run did not settle")


with patch("app.ai.service._write_audit_record"), TestClient(app) as client:
    created = client.post("/games/interactive", json={
        "character_id": 1, "seed": 12, "ai_mode": "offline"
    }).json()
    game_id = created["game_id"]
    state = wait(client, created["run_state_url"])
    leaked = state["last_action"]
    assert leaked["action"] == "SELECT_STRATEGY"
    assert games.get(game_id).players[leaked["player_id"]].role == Role.MAFIA_BOSS
    assert client.get(created["public_state_url"]).json()["revealed_roles"] == {}
    emit("public_role_leak", last_action=leaked, authentication="none")

    predicted = list(ROLES)
    random.Random(12).shuffle(predicted)
    assert predicted == [player.role for player in games.get(game_id).players.values()]
    emit("client_seed_predicts_all_roles", matching_roles=len(predicted))

    result = client.post(f"/game/{game_id}/run/cancel")
    assert result.status_code == 200
    assert client.get(created["run_state_url"]).json()["status"] == "CANCELLED"
    emit("unauthenticated_cancel", http=result.status_code, status="CANCELLED")

    created = client.post("/games/interactive", json={
        "character_id": 1, "seed": 12, "ai_mode": "offline"
    }).json()
    game_id = created["game_id"]
    wait(client, created["run_state_url"])
    headers = {"X-Player-Token": created["human"]["token"]}
    payload = {"action": "ROLE_CLAIM", "claimed_role": "CITIZEN"}
    generic = client.post(f"/game/{game_id}/player/P1/action", headers=headers, json=payload)
    retry = client.post(f"/game/{game_id}/interactive/action", headers=headers, json=payload)
    observation = client.get(created["observation_url"], headers=headers).json()
    run = ai_runs.get(game_id)
    assert generic.status_code == 200 and retry.status_code == 409
    assert run.status == "WAITING_FOR_HUMAN" and run.task.done()
    assert run.awaiting_actions == ["ROLE_CLAIM"] and observation["available_actions"] == []
    emit("generic_gateway_stall", accepted=generic.status_code, retry=retry.status_code,
         status=run.status, advertised=run.awaiting_actions, available=observation["available_actions"])


async def investigate_twice():
    engine = GameEngine()
    game = engine.create_game([PlayerType.AI] * 7, fixed_roles=[
        Role.CITIZEN, Role.MAFIA_BOSS, Role.MAFIA_DEPUTY,
        Role.DOCTOR, Role.DETECTIVE, Role.CITIZEN, Role.CITIZEN,
    ])
    game.phase = Phase.NIGHT_ACTION
    runner = build_runner(engine, game, mode="offline", settings=None, live_action_budget=1)
    detective = runner.agents["P5"]
    first = await detective.decide(runner.observation("P5"))
    engine.submit_action(game, "P5", first.action, first.payload)
    engine.submit_action(game, "P4", "PROTECT", {"target": "P6"})
    engine.submit_action(game, "P2", "KILL", {"target": "P6"})
    assert game.players["P5"].investigations[0].target == "P1"
    assert game.players["P5"].investigations[0].result == Role.CITIZEN
    # Isolate the next night's choice; all players survived the resolved night.
    game.phase = Phase.NIGHT_ACTION
    game.night_actions.clear()
    second = await detective.decide(runner.observation("P5"))
    assert first.payload["target"] == second.payload["target"] == "P1"
    emit("fallback_reinvestigates_known_citizen", first=first.payload, second=second.payload,
         living_uninvestigated_mafia=["P2", "P3"])


asyncio.run(investigate_twice())
