from __future__ import annotations

import json
import time

from fastapi.testclient import TestClient

from app.domain import Faction
from app.ai.providers import ProviderError
import app.main as main_module
from app.main import ai_runs, app, games, runtime
from app.persistence import snapshot


def test_offline_ai_game_lifecycle_and_public_stream():
    with TestClient(app) as client:
        created_response = client.post(
            "/games/ai",
            json={"mode": "offline", "live_action_budget": 1},
        )
        assert created_response.status_code == 202
        created = created_response.json()
        assert "player_credentials" not in created

        run_state = None
        for _ in range(40):
            run_state = client.get(created["run_state_url"]).json()
            if run_state["status"] in {"COMPLETED", "FAILED", "CANCELLED"}:
                break
            time.sleep(0.025)
        assert run_state is not None
        assert run_state["status"] == "COMPLETED"
        assert run_state["summary"]["actions"] > 0

        public = client.get(created["public_state_url"]).json()
        assert public["phase"] == "GAME_OVER"
        assert public["winner"] in {"MAFIA", "CITIZEN"}

        with client.stream("GET", created["stream_url"]) as response:
            stream = "".join(response.iter_text())
        assert response.status_code == 200
        assert "event: game-event" in stream
        assert "event: run-state" in stream
        assert "event: stream-end" in stream
        assert "INVESTIGATION_RESULT" not in stream


def test_frontend_is_served_and_root_redirects():
    with TestClient(app, follow_redirects=False) as client:
        root = client.get("/")
        assert root.status_code in {302, 307}
        assert root.headers["location"] == "/ui/"
        ui = client.get("/ui/")
        assert ui.status_code == 200
        assert "Palermo Nights" in ui.text
        font = client.get("/ui/fonts/Vazirmatn-wght.woff2")
        assert font.status_code == 200
        assert font.headers["content-type"] == "font/woff2"


def test_interactive_game_has_one_human_and_waits_for_their_claim(seeded_api_game):
    seeded_api_game(12)
    with TestClient(app) as client:
        created_response = client.post(
            "/games/interactive",
            json={
                "language": "en",
                "character_id": 4,
                "ai_mode": "offline",
            },
        )
        assert created_response.status_code == 202
        created = created_response.json()
        assert created["human"]["player_id"] == "P1"
        assert "player_credentials" not in created
        assert created["ai_mode"] == "offline"

        headers = {"X-Player-Token": created["human"]["token"]}
        private = client.get(created["private_state_url"], headers=headers)
        assert private.status_code == 200

        observation = client.get(created["observation_url"], headers=headers)
        assert observation.status_code == 200
        assert set(observation.json()) == {
            "player_id", "player_names", "public_state", "private_state",
            "available_actions", "events", "night_replay",
        }

        run_state = None
        for _ in range(80):
            run_state = client.get(created["run_state_url"], headers=headers).json()
            if run_state["status"] == "WAITING_FOR_HUMAN":
                break
            time.sleep(0.01)
        assert run_state is not None
        assert run_state["ai_model"] == "deterministic-fallback"
        assert ai_runs.get(created["game_id"]).awaiting_actions == ["ROLE_CLAIM"]
        names = ai_runs.get(created["game_id"]).runner.agents["P2"].player_names
        assert names["P1"] == "Marco Conti"
        assert names["P2"] == "Matteo Ricci"

        claim = client.post(
            f"/game/{created['game_id']}/interactive/action",
            headers=headers,
            json={"action": "ROLE_CLAIM", "claimed_role": "DETECTIVE"},
        )
        assert claim.status_code == 200

        public = client.get(created["public_state_url"]).json()
        assert public["role_claims"]["P1"] == "DETECTIVE"


def test_byok_key_is_request_scoped_and_never_persisted(monkeypatch):
    secret = "sk-test-participant-secret-123456789"
    observed = {}

    async def one_turn(run, runner, **_):
        provider = next(iter(runner.agents.values())).provider.providers[0]
        observed["key"] = provider.config.api_key
        observed["snapshot"] = json.dumps(snapshot(games.get(run.game_id), run))
        run.status = "WAITING_FOR_HUMAN"
        run.awaiting_actions = ["ROLE_CLAIM"]

    monkeypatch.setattr(main_module, "execute_run", one_turn)
    with TestClient(app) as client:
        created = client.post(
            "/games/interactive",
            json={"language": "en", "character_id": 1, "ai_mode": "luna"},
        ).json()
        headers = {"X-Player-Token": created["human"]["token"]}
        response = client.post(
            f"/game/{created['game_id']}/interactive/continue",
            headers=headers,
            json={"player_api_key": secret},
        )
        assert response.status_code == 200
        assert observed["key"] == secret
        assert secret not in observed["snapshot"]
        assert next(iter(ai_runs.get(created["game_id"]).runner.agents.values())).provider.provider_name == "offline"
        assert secret not in json.dumps(runtime.store.all())


def test_rejected_byok_key_leaves_game_retryable_and_scrubs_runner(monkeypatch):
    secret = "sk-test-rejected-secret-123456789"

    async def reject_turn(*_, **__):
        raise ProviderError("invalid key")

    monkeypatch.setattr(main_module, "execute_run", reject_turn)
    with TestClient(app) as client:
        created = client.post(
            "/games/interactive",
            json={"language": "en", "character_id": 1, "ai_mode": "luna"},
        ).json()
        response = client.post(
            f"/game/{created['game_id']}/interactive/continue",
            headers={"X-Player-Token": created["human"]["token"]},
            json={"player_api_key": secret},
        )
        assert response.status_code == 422
        run = ai_runs.get(created["game_id"])
        assert run.status == "QUEUED"
        assert next(iter(run.runner.agents.values())).provider.provider_name == "offline"
        assert secret not in json.dumps(runtime.store.all())


def test_interactive_offline_match_resumes_until_game_over():
    with TestClient(app) as client:
        created = client.post(
            "/games/interactive",
            json={"language": "de", "character_id": 2, "ai_mode": "offline"},
        ).json()
        game_id = created["game_id"]
        headers = {"X-Player-Token": created["human"]["token"]}

        for _ in range(80):
            for _ in range(80):
                run_state = client.get(created["run_state_url"], headers=headers).json()
                if run_state["status"] in {"WAITING_FOR_HUMAN", "COMPLETED", "FAILED"}:
                    break
                time.sleep(0.001)
            run = ai_runs.get(game_id)
            assert run.status != "FAILED"
            if run.status == "COMPLETED":
                break

            game = games.get(game_id)
            action = run.awaiting_actions[0]
            payload: dict[str, str] = {"action": action}
            if action == "SELECT_STRATEGY":
                payload["strategy"] = "USE_CONTRADICTION"
            elif action == "ROLE_CLAIM":
                payload["claimed_role"] = "CITIZEN"
            elif action in {"SPEAK", "ANSWER"}:
                payload["text"] = "A concise public statement."
            elif action == "SUBMIT_VOTE_DECISION":
                choices = [
                    pid for pid, player in game.players.items()
                    if player.alive and pid != "P1"
                ]
                payload["vote_target"] = choices[0]
                payload["trusted_player"] = choices[-1]
                alive_mafia = sum(
                    player.alive and player.faction == Faction.MAFIA
                    for player in game.players.values()
                )
                if alive_mafia > 1:
                    payload["suspect_2"] = choices[1]
            elif action == "KILL":
                payload["target"] = next(
                    pid for pid, player in game.players.items()
                    if player.alive and player.faction == Faction.CITIZEN
                )
            elif action in {"PROTECT", "INVESTIGATE"}:
                human = game.players["P1"]
                payload["target"] = next(
                    pid for pid, player in game.players.items()
                    if player.alive
                    and not player.shunned
                    and (action != "PROTECT" or pid != human.previous_protection_target)
                )
            response = client.post(
                f"/game/{game_id}/interactive/action",
                headers=headers,
                json=payload,
            )
            assert response.status_code == 200, response.text

        assert ai_runs.get(game_id).status == "COMPLETED"
        assert games.get(game_id).phase.value == "GAME_OVER"


def test_human_mafia_boss_selects_strategy_before_claiming_role(seeded_api_game):
    seeded_api_game(3)
    with TestClient(app) as client:
        created = client.post(
            "/games/interactive",
            json={"language": "fa", "character_id": 1, "ai_mode": "offline"},
        ).json()
        headers = {"X-Player-Token": created["human"]["token"]}

        for _ in range(80):
            run_state = client.get(created["run_state_url"], headers=headers).json()
            if run_state["status"] == "WAITING_FOR_HUMAN":
                break
            time.sleep(0.005)
        assert ai_runs.get(created["game_id"]).awaiting_actions == ["SELECT_STRATEGY"]
        observation = client.get(created["observation_url"], headers=headers).json()
        assert observation["available_actions"] == ["SELECT_STRATEGY"]

        selected = client.post(
            f"/game/{created['game_id']}/interactive/action",
            headers=headers,
            json={"action": "SELECT_STRATEGY", "strategy": "CREATE_TWO_SIDES"},
        )
        assert selected.status_code == 200

        for _ in range(80):
            run_state = client.get(created["run_state_url"], headers=headers).json()
            if run_state["status"] == "WAITING_FOR_HUMAN":
                break
            time.sleep(0.005)
        assert ai_runs.get(created["game_id"]).awaiting_actions == ["ROLE_CLAIM"]
        assert games.get(created["game_id"]).mafia_strategy == "CREATE_TWO_SIDES"
