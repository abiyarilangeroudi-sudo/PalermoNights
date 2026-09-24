from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def create_game():
    response = client.post(
        "/games",
        json={
            "player_types": ["HUMAN", "AI", "AI", "HUMAN", "AI", "AI", "HUMAN"],
            "seed": 11,
        },
    )
    assert response.status_code == 201
    return response.json()


def test_create_and_fetch_filtered_state():
    created = create_game()
    game_id = created["game_id"]
    credentials = {item["player_id"]: item["token"] for item in created["player_credentials"]}

    public = client.get(f"/game/{game_id}/public-state")
    assert public.status_code == 200
    assert public.json()["role_claims"] == {}
    assert public.json()["revealed_roles"] == {}
    assert all("role" not in player for player in public.json()["players"].values())

    private = client.get(
        f"/game/{game_id}/player/P1/private-state",
        headers={"X-Player-Token": credentials["P1"]},
    )
    assert private.status_code == 200
    assert private.json()["role"] in {
        "MAFIA_BOSS", "MAFIA_DEPUTY", "DOCTOR", "DETECTIVE", "CITIZEN"
    }

    cross_player = client.get(
        f"/game/{game_id}/player/P2/private-state",
        headers={"X-Player-Token": credentials["P1"]},
    )
    assert cross_player.status_code == 401
    assert cross_player.json()["error"] == "PLAYER_AUTHENTICATION_FAILED"


def test_available_actions_and_invalid_action_error_contract():
    created = create_game()
    game_id = created["game_id"]
    credentials = {item["player_id"]: item["token"] for item in created["player_credentials"]}

    boss_id = None
    for player_id, token in credentials.items():
        private = client.get(
            f"/game/{game_id}/player/{player_id}/private-state",
            headers={"X-Player-Token": token},
        ).json()
        if private["role"] == "MAFIA_BOSS":
            boss_id = player_id
            break
    assert boss_id is not None

    available = client.get(
        f"/game/{game_id}/player/{boss_id}/available-actions",
        headers={"X-Player-Token": credentials[boss_id]},
    )
    assert "SELECT_STRATEGY" in available.json()["actions"]

    invalid = client.post(
        f"/game/{game_id}/player/{boss_id}/action",
        headers={"X-Player-Token": credentials[boss_id]},
        json={"action": "KILL", "target": "P1"},
    )
    assert invalid.status_code == 409
    assert invalid.json()["error"] == "ACTION_NOT_AVAILABLE_IN_CURRENT_STATE"


def test_public_event_feed_never_returns_engine_events():
    created = create_game()
    response = client.get(f"/game/{created['game_id']}/events")
    assert response.status_code == 200
    events = response.json()["events"]
    assert [event["type"] for event in events] == ["GAME_CREATED"]
    assert all(event["visibility"] == "PUBLIC" for event in events)
