from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .domain import PlayerType, RuleViolation
from .engine import GameEngine
from .repository import InMemoryGameRepository


class CreateGameRequest(BaseModel):
    player_types: list[PlayerType] = Field(default_factory=lambda: [PlayerType.HUMAN] * 7)
    seed: int | None = None


class ActionRequest(BaseModel):
    action: str
    target: str | None = None
    text: str | None = None
    claimed_role: str | None = None
    strategy: str | None = None
    vote_target: str | None = None
    suspect_2: str | None = None
    trusted_player: str | None = None
    question_id: str | None = None


app = FastAPI(title="Palermo Nights", version="0.1.0")
engine = GameEngine()
games = InMemoryGameRepository()


@app.exception_handler(RuleViolation)
async def rule_violation_handler(_, exc: RuleViolation):
    status = 404 if exc.code in {"GAME_NOT_FOUND", "PLAYER_NOT_FOUND"} else 401 if exc.code == "PLAYER_AUTHENTICATION_FAILED" else 409
    return JSONResponse(
        status_code=status, content={"success": False, "error": exc.code, "detail": exc.message}
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/games", status_code=201)
def create_game(request: CreateGameRequest) -> dict[str, Any]:
    game = engine.create_game(request.player_types, seed=request.seed)
    games.add(game)
    # Tokens are returned only once to the trusted game creator for distribution.
    return {
        "game_id": game.game_id,
        "phase": game.phase.value,
        "player_credentials": [
            {"player_id": p.player_id, "token": p.token, "player_type": p.player_type.value}
            for p in game.players.values()
        ],
    }


@app.get("/game/{game_id}/public-state")
def public_state(game_id: str) -> dict[str, Any]:
    return engine.public_state(games.get(game_id))


@app.get("/game/{game_id}/player/{player_id}/private-state")
def private_state(
    game_id: str, player_id: str, x_player_token: str | None = Header(default=None)
) -> dict[str, Any]:
    game = games.get(game_id)
    engine.authenticate(game, player_id, x_player_token)
    return engine.private_state(game, player_id)


@app.get("/game/{game_id}/player/{player_id}/available-actions")
def available_actions(
    game_id: str, player_id: str, x_player_token: str | None = Header(default=None)
) -> dict[str, Any]:
    game = games.get(game_id)
    engine.authenticate(game, player_id, x_player_token)
    return {"actions": engine.available_actions(game, player_id)}


@app.post("/game/{game_id}/player/{player_id}/action")
def take_action(
    game_id: str,
    player_id: str,
    request: ActionRequest,
    x_player_token: str | None = Header(default=None),
) -> dict[str, Any]:
    game = games.get(game_id)
    engine.authenticate(game, player_id, x_player_token)
    with games.lock:
        return engine.submit_action(game, player_id, request.action, request.model_dump(exclude_none=True))


@app.get("/game/{game_id}/events")
def events(
    game_id: str,
    player_id: str | None = Query(default=None),
    x_player_token: str | None = Header(default=None),
) -> dict[str, Any]:
    game = games.get(game_id)
    if player_id is not None:
        engine.authenticate(game, player_id, x_player_token)
    elif x_player_token is not None:
        raise HTTPException(status_code=400, detail="player_id is required with X-Player-Token")
    return {"events": engine.visible_events(game, player_id)}
