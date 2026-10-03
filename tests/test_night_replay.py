import json

import pytest
from fastapi.testclient import TestClient

from app.ai.service import AIRun
from app.domain import Phase, PlayerType, Role
from app.main import app, engine, games, ai_runs


@pytest.mark.parametrize("reason", ["PROTECTED", "KILLED", "ATTACKER_BLOCKED", "NO_ACTIVE_ATTACKER"])
def test_night_reason_is_internal_until_authenticated_game_over(reason):
    game = engine.create_game([PlayerType.HUMAN] * 7, seed=42)
    by_role = {p.role: p for p in game.players.values()}
    boss, deputy, doctor = (by_role[r] for r in [Role.MAFIA_BOSS, Role.MAFIA_DEPUTY, Role.DOCTOR])
    target = by_role[Role.CITIZEN].player_id
    game.phase = Phase.NIGHT_ACTION
    if reason == "NO_ACTIVE_ATTACKER":
        boss.alive = deputy.alive = False
    elif reason == "ATTACKER_BLOCKED":
        boss.shunned = True
    else:
        game.night_actions[boss.player_id] = target
    game.night_actions[doctor.player_id] = target if reason == "PROTECTED" else doctor.player_id
    engine._resolve_night(game)
    internal = next(e for e in game.events if e.type == "NIGHT_RESOLUTION")
    assert internal.payload["reason"] == reason
    # Force pre-end view even when no mafia remains, to verify the access boundary.
    game.phase = Phase.DAY_DISCUSSION
    games.add(game)
    ai_runs.add(AIRun(game.game_id, "offline", human_player_id="P1"))
    path = f"/game/{game.game_id}/player/P1/observation"
    headers = {"X-Player-Token": game.players["P1"].token}
    with TestClient(app) as client:
        assert client.get(path, headers=headers).json()["night_replay"] == []
        for pid in game.players:
            assert "NIGHT_RESOLUTION" not in json.dumps(engine.visible_events(game, pid))
        game.phase = Phase.GAME_OVER
        assert client.get(path).status_code in {401, 403}
        assert client.get(path, headers={"X-Player-Token": "wrong"}).status_code in {401, 403}
        replay = client.get(path, headers=headers).json()["night_replay"]
        assert replay == [{"round": 1, **internal.payload}]
        assert "attack_target" not in client.get(f"/game/{game.game_id}/events").text
        assert "attack_target" not in client.get(f"/game/{game.game_id}/public-state").text


def test_old_game_does_not_invent_night_explanation():
    game = engine.create_game([PlayerType.HUMAN] * 7)
    game.phase = Phase.GAME_OVER
    engine._event(game, "NIGHT_RESULT", {"result": "NO_DEATH"})
    assert engine.completed_night_replay(game) == []
