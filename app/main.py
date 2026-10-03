from __future__ import annotations

import asyncio
import json
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from .ai.config import AISettings, ConfigurationError
from .ai.service import (
    AIRun,
    AIRunRegistry,
    build_runner,
    execute_run,
    update_run_progress,
)
from .domain import Action, CLAIMABLE_ROLES, PlayerType, RuleViolation
from .engine import GameEngine
from .repository import InMemoryGameRepository


class CreateGameRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    player_types: list[PlayerType] = Field(default_factory=lambda: [PlayerType.HUMAN] * 7)


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
    model_config = ConfigDict(extra="forbid")
    mode: Literal["offline", "live"] = "offline"
    live_action_budget: int = Field(default=1, ge=0, le=100)


class CreateInteractiveGameRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    language: Literal["fa", "en", "de"] = "fa"
    character_id: int = Field(ge=1, le=7)
    ai_mode: Literal["luna", "offline"] = "luna"


app = FastAPI(title="Palermo Nights", version="0.1.0")
engine = GameEngine()
games = InMemoryGameRepository()
ai_runs = AIRunRegistry()

CHARACTER_NAMES = {
    1: "Matteo Ricci",
    2: "Vittorio Moretti",
    3: "Rosa Greco",
    4: "Marco Conti",
    5: "Luca Romano",
    6: "Isabella Bellini",
    7: "Elena Rossi",
}


def interactive_player_names(character_id: int) -> dict[str, str]:
    ordered_ids = [character_id, *(item for item in CHARACTER_NAMES if item != character_id)]
    return {
        f"P{index}": CHARACTER_NAMES[item]
        for index, item in enumerate(ordered_ids, start=1)
    }


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
    game = engine.create_game(request.player_types)
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
    game = engine.create_game([PlayerType.AI] * 7)
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
        "control_token": run.control_token,
        "status": run.status,
        "public_state_url": f"/game/{game.game_id}/public-state",
        "run_state_url": f"/game/{game.game_id}/run-state",
        "stream_url": f"/game/{game.game_id}/stream",
    }


@app.post("/games/interactive", status_code=202)
async def create_interactive_game(request: CreateInteractiveGameRequest) -> dict[str, Any]:
    settings = None
    mode = "offline"
    ai_model = "deterministic-fallback"
    if request.ai_mode == "luna":
        try:
            settings = AISettings.for_openai_players(player_count=6, env_file=".env")
            mode = "live"
            ai_model = settings.player_providers[0].model
        except ConfigurationError:
            # The game remains playable when a deployment has no OpenAI key.
            mode = "offline"

    game = engine.create_game(
        [PlayerType.HUMAN, *([PlayerType.AI] * 6)],
    )
    games.add(game)
    human = game.players["P1"]

    run = AIRun(
        game_id=game.game_id,
        mode=mode,
        human_player_id=human.player_id,
        human_token=human.token,
        character_id=request.character_id,
        language=request.language,
        ai_model=ai_model,
    )
    runner = build_runner(
        engine,
        game,
        mode=mode,
        settings=settings,
        live_action_budget=None,
        language=request.language,
        player_names=interactive_player_names(request.character_id),
        on_entry=lambda entry: update_run_progress(run, entry),
    )
    run.runner = runner
    ai_runs.add(run)
    run.task = asyncio.create_task(execute_run(run, runner))
    return {
        "game_id": game.game_id,
        "status": run.status,
        "language": request.language,
        "character_id": request.character_id,
        "ai_mode": mode,
        "ai_model": ai_model,
        "human": {"player_id": human.player_id, "token": human.token},
        "public_state_url": f"/game/{game.game_id}/public-state",
        "private_state_url": (
            f"/game/{game.game_id}/player/{human.player_id}/private-state"
        ),
        "observation_url": (
            f"/game/{game.game_id}/player/{human.player_id}/observation"
        ),
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


@app.get("/game/{game_id}/player/{player_id}/observation")
def player_observation(
    game_id: str, player_id: str, x_player_token: str | None = Header(default=None)
) -> dict[str, Any]:
    """Return the same filtered information boundary used by an AI agent."""
    game = games.get(game_id)
    engine.authenticate(game, player_id, x_player_token)
    run = ai_runs.get(game_id)
    observation = (
        run.runner.observation(player_id)
        if run.runner is not None
        else None
    )
    return {
        "player_id": player_id,
        "player_names": interactive_player_names(run.character_id or 1),
        "public_state": observation.public_state if observation else engine.public_state(game),
        "private_state": observation.private_state if observation else engine.private_state(game, player_id),
        "available_actions": observation.available_actions if observation else [
            action for action in engine.available_actions(game, player_id)
            if action != Action.SET_WILL.value
        ],
        "events": observation.events if observation else engine.visible_events(game, player_id),
        "night_replay": engine.completed_night_replay(game),
    }


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
        if ai_runs.contains(game_id):
            raise RuleViolation("USE_INTERACTIVE_ACTION_ENDPOINT")
        return engine.submit_action(game, player_id, request.action, request.model_dump(exclude_none=True))


@app.post("/game/{game_id}/interactive/action")
async def take_interactive_action(
    game_id: str,
    request: ActionRequest,
    x_player_token: str | None = Header(default=None),
) -> dict[str, Any]:
    game = games.get(game_id)
    run = ai_runs.get(game_id)
    player_id = run.human_player_id
    if player_id is None:
        raise HTTPException(status_code=409, detail="game is not interactive")
    engine.authenticate(game, player_id, x_player_token)
    if run.status != "WAITING_FOR_HUMAN":
        raise HTTPException(status_code=409, detail="the game is not waiting for the human")
    payload = request.model_dump(exclude_none=True)
    payload.pop("action", None)
    if request.action == Action.ROLE_CLAIM:
        allowed_claims = {role.value for role in CLAIMABLE_ROLES}
        if request.claimed_role not in allowed_claims:
            raise RuleViolation("INVALID_ROLE_CLAIM")
    elif request.action == Action.ANSWER:
        if not any(
            question.target == player_id and not question.answered
            for question in game.questions
        ):
            raise RuleViolation("NO_PENDING_QUESTION")
        # ANSWER is intentionally a batch action; the engine resolves every pending
        # question for this player in a single turn.
        payload.pop("question_id", None)

    with games.lock:
        result = run.runner.submit_participant_decision(
            player_id,
            request.action,
            payload,
            source="human",
            required_actions=run.awaiting_actions,
        )
    run.status = "QUEUED"
    run.awaiting_actions.clear()
    run.task = asyncio.create_task(execute_run(run, run.runner))
    return {**result, "run_state_url": f"/game/{game_id}/run-state"}

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
async def ai_run_state(
    game_id: str, x_player_token: str | None = Header(default=None)
) -> dict[str, Any]:
    game = games.get(game_id)
    run = ai_runs.get(game_id)
    if x_player_token is not None:
        engine.authenticate(game, run.human_player_id, x_player_token)
    return run.public_dict(participant=x_player_token is not None)


@app.post("/game/{game_id}/run/cancel")
async def cancel_ai_run(
    game_id: str,
    x_player_token: str | None = Header(default=None),
    x_run_token: str | None = Header(default=None),
) -> dict[str, Any]:
    run = ai_runs.get(game_id)
    if run.human_player_id is not None:
        engine.authenticate(games.get(game_id), run.human_player_id, x_player_token)
    elif not x_run_token or not secrets.compare_digest(run.control_token, x_run_token):
        raise HTTPException(status_code=401, detail="run authentication failed")
    if run.status not in {"QUEUED", "RUNNING", "WAITING_FOR_HUMAN"}:
        raise HTTPException(status_code=409, detail="run is not active")
    if run.task and not run.task.done():
        run.task.cancel()
        try:
            await run.task
        except asyncio.CancelledError:
            pass  # The task may have been cancelled before execute_run started.
    run.status = "CANCELLED"
    run.awaiting_actions.clear()
    run.finished_at = datetime.now(UTC).isoformat()
    return {"success": True, "status": run.status}


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
