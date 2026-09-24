from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .ai.config import AISettings, ConfigurationError
from .ai.service import (
    AIRun,
    AIRunRegistry,
    build_runner,
    execute_run,
    update_run_progress,
)
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


class CreateAIGameRequest(BaseModel):
    mode: Literal["offline", "live"] = "offline"
    seed: int | None = None
    live_action_budget: int = Field(default=1, ge=0, le=100)


app = FastAPI(title="Palermo Nights", version="0.1.0")
engine = GameEngine()
games = InMemoryGameRepository()
ai_runs = AIRunRegistry()


@app.exception_handler(RuleViolation)
async def rule_violation_handler(_, exc: RuleViolation):
    if exc.code in {"GAME_NOT_FOUND", "PLAYER_NOT_FOUND", "AI_RUN_NOT_FOUND"}:
        status = 404
    elif exc.code == "PLAYER_AUTHENTICATION_FAILED":
        status = 401
    else:
        status = 409
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


@app.post("/games/ai", status_code=202)
async def create_ai_game(request: CreateAIGameRequest) -> dict[str, Any]:
    settings = None
    if request.mode == "live":
        try:
            settings = AISettings.from_environment(env_file=".env")
        except ConfigurationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    game = engine.create_game([PlayerType.AI] * 7, seed=request.seed)
    games.add(game)
    run = AIRun(game_id=game.game_id, mode=request.mode)
    ai_runs.add(run)
    budget = None if request.live_action_budget == 0 else request.live_action_budget
    runner = build_runner(
        engine,
        game,
        mode=request.mode,
        settings=settings,
        live_action_budget=budget,
        on_entry=lambda entry: update_run_progress(run, entry),
    )
    run.task = asyncio.create_task(execute_run(run, runner))
    return {
        "game_id": game.game_id,
        "mode": request.mode,
        "status": run.status,
        "public_state_url": f"/game/{game.game_id}/public-state",
        "run_state_url": f"/game/{game.game_id}/run-state",
        "stream_url": f"/game/{game.game_id}/stream",
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


@app.get("/game/{game_id}/run-state")
async def ai_run_state(game_id: str) -> dict[str, Any]:
    games.get(game_id)
    return ai_runs.get(game_id).public_dict()


@app.post("/game/{game_id}/run/cancel")
async def cancel_ai_run(game_id: str) -> dict[str, Any]:
    run = ai_runs.get(game_id)
    if run.status not in {"QUEUED", "RUNNING"}:
        raise HTTPException(status_code=409, detail="run is not active")
    if run.task:
        run.task.cancel()
    return {"success": True, "status": "CANCELLING"}


@app.get("/game/{game_id}/stream")
async def stream_game(game_id: str, request: Request):
    game = games.get(game_id)
    run = ai_runs.get(game_id)

    async def generate():
        event_cursor = 0
        last_run_state = ""
        idle_ticks = 0
        while True:
            if await request.is_disconnected():
                break
            public_events = engine.visible_events(game)
            for event in public_events[event_cursor:]:
                yield (
                    f"id: {event['event_id']}\n"
                    "event: game-event\n"
                    f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                )
            event_cursor = len(public_events)
            run_state = json.dumps(run.public_dict(), ensure_ascii=False, sort_keys=True)
            if run_state != last_run_state:
                yield f"event: run-state\ndata: {run_state}\n\n"
                last_run_state = run_state
                idle_ticks = 0
            else:
                idle_ticks += 1
            if idle_ticks >= 30:
                yield ": heartbeat\n\n"
                idle_ticks = 0
            if run.status in {"COMPLETED", "FAILED", "CANCELLED"} and event_cursor >= len(public_events):
                yield "event: stream-end\ndata: {}\n\n"
                break
            await asyncio.sleep(0.5)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/", include_in_schema=False)
async def root_redirect():
    return RedirectResponse(url="/ui/")


frontend_path = Path(__file__).resolve().parent.parent / "Frontend"
if frontend_path.exists():
    app.mount("/ui", StaticFiles(directory=frontend_path, html=True), name="ui")
