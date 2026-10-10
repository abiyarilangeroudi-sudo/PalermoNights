from __future__ import annotations

import asyncio
import json
import os
import secrets
import copy
import hashlib
from dataclasses import replace
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from collections.abc import Mapping
from typing import Any, Literal

from fastapi import FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from .ai.config import AISettings, ConfigurationError, ProviderConfig
from .ai.service import (
    AIRun,
    AIRunRegistry,
    build_runner,
    execute_run,
    audit_entry,
)
from .ai.providers import ProviderError
from .domain import Action, CLAIMABLE_ROLES, PlayerType, RuleViolation
from .engine import GameEngine
from .repository import InMemoryGameRepository
from .persistence import SnapshotStore, snapshot
from .runtime import GameRuntime
from .admission import Admission, issue_session, limit


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
    request_id: str | None = Field(default=None, min_length=8, max_length=128)
    expected_event_id: str | None = Field(default=None, max_length=128)


class CreateAIGameRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["offline", "live"] = "offline"
    live_action_budget: int = Field(default=1, ge=0, le=100)


class CreateInteractiveGameRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    language: Literal["fa", "en", "de"] = "fa"
    character_id: int = Field(ge=1, le=7)
    ai_mode: Literal["luna", "offline"] = "luna"


class ContinueInteractiveGameRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: Literal["openai", "gemini", "openrouter"] = "openai"
    model: str = Field(default="gpt-5.6-luna", min_length=2, max_length=120, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]{1,119}$")
    player_api_key: SecretStr = Field(min_length=20, max_length=512)


@asynccontextmanager
async def lifespan(app):
    if os.getenv("PALERMO_CLOUDFLARE_WORKER") != "1":
        from dotenv import load_dotenv
        load_dotenv(".env", override=False)
        store = SnapshotStore(os.getenv("PALERMO_DB_PATH", ".palermo-data/games.sqlite3"))
        store.open()
        runtime.store = store
        try:
            for value in store.all():
                runtime.restore(value)
            maintenance = asyncio.create_task(runtime.maintain())
            yield
        finally:
            if "maintenance" in locals():
                maintenance.cancel()
                await asyncio.gather(maintenance, return_exceptions=True)
            try:
                await runtime.stop()
            finally:
                runtime.store = None
                store.close()
    else:
        yield


app = FastAPI(title="Palermo Nights", version="0.1.0", lifespan=lifespan)
engine = GameEngine()
games = InMemoryGameRepository()
ai_runs = AIRunRegistry()
runtime = GameRuntime(engine, games, ai_runs)
admission = Admission(runtime)
from .ai import library as strategy_library
strategy_library._approved = lambda: [c['review'] for c in runtime.store.lessons() if c.get('review', {}).get('status') == 'reviewed'] if runtime.store else []


CHARACTER_NAMES = {
    1: "Matteo Ricci",
    2: "Vittorio Moretti",
    3: "Rosa Greco",
    4: "Marco Conti",
    5: "Luca Romano",
    6: "Isabella Bellini",
    7: "Elena Rossi",
}

AI_ENVIRONMENT_NAMES = (
    "OPENAI_API_KEY",
    "OPENAI_PLAYER_MODEL",
    "OPENAI_ANALYST_MODEL",
    "OPENAI_BASE_URL",
    "OPENAI_REASONING_EFFORT",
    "LLM_MIN_REQUEST_INTERVAL_SECONDS",
    "LLM_MAX_OUTPUT_TOKENS",
    "LLM_SPEAK_MAX_OUTPUT_TOKENS",
    "LLM_REQUEST_TIMEOUT_SECONDS",
    "LLM_DECISION_TIMEOUT_SECONDS",
    "TYPESAFE_DECISION_TIMEOUT_SECONDS",
    "LLM_ANALYST_MAX_OUTPUT_TOKENS",
)


def request_ai_environment(request: Request) -> Mapping[str, str] | None:
    """Read AI configuration from Cloudflare bindings when they are present."""
    bindings = request.scope.get("env")
    if bindings is None:
        return None

    values = dict(os.environ)
    for name in AI_ENVIRONMENT_NAMES:
        if isinstance(bindings, Mapping):
            value = bindings.get(name)
        else:
            value = getattr(bindings, name, None)
        if value is not None:
            values[name] = str(value)
    return values


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


@app.post("/session")
async def create_session(request: Request, response: Response):
    return issue_session(request, response)


@app.get("/health")
async def health(request: Request) -> dict[str, str]:
    binding = getattr(request.scope.get("env"), "CF_VERSION_METADATA", None)
    return {"status": "ok", "release": "2026-10-10-remembered-byok-dialogue",
            "deployment_id": str(getattr(binding, "id", "local")),
            "storage": "durable-object" if runtime.external_scheduler else "sqlite"}


@app.post("/games", status_code=201)
async def create_game(request: CreateGameRequest, http_request: Request) -> dict[str, Any]:
    with games.lock:
        admission.admit(http_request)
    game = engine.create_game(request.player_types)
    games.add(game)
    try:
        runtime.save(game.game_id)
    except Exception:
        games._games.pop(game.game_id, None)
        raise
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
async def create_ai_game(
    request: CreateAIGameRequest, http_request: Request
) -> dict[str, Any]:
    owner = admission.admit(http_request, live=request.mode == "live")
    settings = None
    if request.mode == "live":
        try:
            runtime_environment = request_ai_environment(http_request)
            settings = AISettings.from_environment(
                env_file=".env" if runtime_environment is None else None,
                environ=runtime_environment,
            )
        except ConfigurationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    game = engine.create_game([PlayerType.AI] * 7)
    games.add(game)
    run = AIRun(game_id=game.game_id, mode=request.mode)
    ai_runs.add(run)
    budget = min(request.live_action_budget or 20, limit("PALERMO_DECISIONS_PER_AGENT", 20))
    run.live_action_budget = budget
    run.owner = owner
    runner = build_runner(
        engine,
        game,
        mode=request.mode,
        settings=settings,
        live_action_budget=budget,
    )
    runtime.start(run, runner)
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
async def create_interactive_game(
    request: CreateInteractiveGameRequest, http_request: Request
) -> dict[str, Any]:
    # Participant-funded games do not consume a deployment provider credential.
    owner = admission.admit(http_request)
    mode = "offline"
    ai_model = "deterministic-fallback"
    if request.ai_mode == "luna":
        runtime_environment = request_ai_environment(http_request) or os.environ
        mode = "live"
        ai_model = runtime_environment.get("OPENAI_PLAYER_MODEL", "gpt-5.6-luna")

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
        ai_provider="openai" if mode == "live" else "offline",
        ai_model=ai_model,
        owner=owner,
        live_action_budget=limit("PALERMO_DECISIONS_PER_AGENT", 20),
        credential_mode="participant" if mode == "live" else "server",
    )
    runner = build_runner(
        engine,
        game,
        mode="offline",
        settings=None,
        live_action_budget=run.live_action_budget,
        language=request.language,
        player_names=interactive_player_names(request.character_id),
    )
    run.runner = runner
    ai_runs.add(run)
    runtime.start(run, runner, schedule=mode != "live")
    return {
        "game_id": game.game_id,
        "status": run.status,
        "language": request.language,
        "character_id": request.character_id,
        "ai_mode": mode,
        "ai_provider": run.ai_provider,
        "ai_model": ai_model,
        "credential_required": mode == "live",
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


def participant_ai_settings(
    http_request: Request, provider: str, model: str, api_key: str,
) -> AISettings:
    """Create request-scoped settings using only allowlisted provider endpoints."""
    values = dict(request_ai_environment(http_request) or os.environ)
    values["OPENAI_API_KEY"] = api_key
    values["OPENAI_BASE_URL"] = "https://api.openai.com/v1"
    base = AISettings.for_openai_players(player_count=6, env_file=None, environ=values)
    provider_config = {
        "openai": ProviderConfig("openai", model, api_key, "https://api.openai.com/v1"),
        "gemini": ProviderConfig("gemini", model, api_key),
        "openrouter": ProviderConfig("openrouter", model, api_key, "https://openrouter.ai/api/v1"),
    }[provider]
    return replace(
        base,
        provider_mode=f"participant-{provider}",
        player_providers=tuple(provider_config for _ in range(6)),
    )


@app.post("/game/{game_id}/interactive/continue")
async def continue_interactive_game(
    game_id: str,
    request: ContinueInteractiveGameRequest,
    http_request: Request,
    x_player_token: str | None = Header(default=None),
) -> dict[str, Any]:
    game = games.get(game_id)
    run = ai_runs.get(game_id)
    if run.human_player_id is None or run.credential_mode != "participant":
        raise HTTPException(status_code=409, detail="participant credentials are not used by this game")
    engine.authenticate(game, run.human_player_id, x_player_token)
    if run.status not in {"QUEUED", "RUNNING"}:
        return run.public_dict(participant=True)
    if run.drive_lock is None:
        run.drive_lock = asyncio.Lock()
    async with run.drive_lock:
        if run.status not in {"QUEUED", "RUNNING"}:
            return run.public_dict(participant=True)
        before = copy.deepcopy(snapshot(game, run))
        try:
            settings = participant_ai_settings(
                http_request, request.provider, request.model,
                request.player_api_key.get_secret_value(),
            )
            runner = runtime.replace_runner(
                run, mode="live", settings=settings, allow_fallback=False,
            )
            await execute_run(run, runner, batch_steps=1, propagate_errors=True)
        except Exception as exc:
            runtime.rollback(run, before)
            runtime.replace_runner(run, mode="offline")
            runtime.save(game_id)
            status = 422 if isinstance(
                exc, (ConfigurationError, ProviderError, TimeoutError, ValueError, KeyError, TypeError)
            ) else 502
            raise HTTPException(
                status_code=status,
                detail="The supplied provider credentials could not complete this turn",
            ) from None
        runtime.replace_runner(run, mode="offline")
        run.ai_provider = request.provider
        run.ai_model = request.model
        runtime.save(game_id)
        return run.public_dict(participant=True)


@app.get("/game/{game_id}/public-state")
async def public_state(game_id: str) -> dict[str, Any]:
    return engine.public_state(games.get(game_id))


@app.get("/game/{game_id}/player/{player_id}/private-state")
async def private_state(
    game_id: str, player_id: str, x_player_token: str | None = Header(default=None)
) -> dict[str, Any]:
    game = games.get(game_id)
    engine.authenticate(game, player_id, x_player_token)
    return engine.private_state(game, player_id)


@app.get("/game/{game_id}/player/{player_id}/available-actions")
async def available_actions(
    game_id: str, player_id: str, x_player_token: str | None = Header(default=None)
) -> dict[str, Any]:
    game = games.get(game_id)
    engine.authenticate(game, player_id, x_player_token)
    return {"actions": engine.available_actions(game, player_id)}


@app.get("/game/{game_id}/player/{player_id}/observation")
async def player_observation(
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
async def take_action(
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
        before = copy.deepcopy(game)
        try:
            result = engine.submit_action(game, player_id, request.action, request.model_dump(exclude_none=True))
            runtime.save(game_id)
        except Exception:
            from dataclasses import fields
            for f in fields(game):
                setattr(game, f.name, getattr(before, f.name))
            raise
        return result


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
    fingerprint = hashlib.sha256(json.dumps(request.model_dump(exclude={"request_id", "expected_event_id"}), sort_keys=True).encode()).hexdigest()
    if request.request_id and request.request_id in run.receipts:
        receipt = run.receipts[request.request_id]
        if receipt["fingerprint"] != fingerprint:
            raise HTTPException(status_code=409, detail="request_id reused with different action")
        return receipt["response"]
    if request.expected_event_id:
        visible = engine.visible_events(game, player_id)
        if not visible or visible[-1]["event_id"] != request.expected_event_id:
            raise HTTPException(status_code=409, detail="stale action; refresh game state")
    if run.status != "WAITING_FOR_HUMAN":
        raise HTTPException(status_code=409, detail="the game is not waiting for the human")
    payload = request.model_dump(exclude_none=True)
    payload.pop("action", None)
    payload.pop("request_id", None)
    payload.pop("expected_event_id", None)
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
        before = copy.deepcopy(snapshot(game, run))
        try:
            result = run.runner.submit_participant_decision(
                player_id, request.action, payload, source="human",
                required_actions=run.awaiting_actions,
            )
            result = {**result, "run_state_url": f"/game/{game_id}/run-state"}
            run.status = "QUEUED"
            run.awaiting_actions.clear()
            if request.request_id:
                run.receipts[request.request_id] = {"fingerprint": fingerprint, "response": result}
            runtime.save(game_id)
        except Exception:
            runtime.rollback(run, before)
            raise
    audit_entry(run, run.runner.transcript[-1])
    runtime.schedule(run)
    return result

class LessonReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=1200)
    observation: str = Field(min_length=1, max_length=1200)
    hypothesis: str = Field(min_length=1, max_length=1200)
    counterexample: str = Field(min_length=1, max_length=1200)
    limitations: str = Field(min_length=1, max_length=1200)


@app.post("/game/{game_id}/analysis/review")
async def review_lesson(game_id: str, review: LessonReviewRequest, x_review_key: str | None = Header(default=None)):
    key = os.getenv("PALERMO_REVIEW_KEY", "")
    if not key or not secrets.compare_digest(key, x_review_key or ""):
        raise HTTPException(401, "review access required")
    from .lesson_review import reviewed_card
    case = strategy_library.analyze_game(games.get(game_id))
    if not case['complete']:
        raise HTTPException(409, "Only completed games can be reviewed")
    case['review'] = reviewed_card(case, review.model_dump())
    runtime.store.update_lesson(case)
    return {"success": True, "version": case['review']['version']}


@app.get("/game/{game_id}/analysis")
async def game_analysis(game_id: str):
    from .ai.library import analyze_game
    game = games.get(game_id)
    if game.phase.value != "GAME_OVER":
        raise HTTPException(409, "Analysis is available after game over")
    return analyze_game(game)


@app.get("/game/{game_id}/events")
async def events(
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
        # Even an idempotent cancellation retry must make the terminal state durable.
        runtime.save(game_id)
        if run.status == "CANCELLED":
            return {"success": True, "status": run.status}
        raise HTTPException(status_code=409, detail="run is not active")
    if run.task and not run.task.done():
        run.task.cancel()
        try:
            await run.task
        except asyncio.CancelledError:
            pass  # The task may have been cancelled before execute_run started.
        except Exception:
            # Its final checkpoint may have failed; the explicit save below must succeed.
            pass
    run.status = "CANCELLED"
    run.awaiting_actions.clear()
    run.finished_at = datetime.now(UTC).isoformat()
    runtime.save(game_id)
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
if os.getenv("PALERMO_CLOUDFLARE_WORKER") != "1" and frontend_path.exists():
    app.mount("/ui", StaticFiles(directory=frontend_path, html=True), name="ui")
