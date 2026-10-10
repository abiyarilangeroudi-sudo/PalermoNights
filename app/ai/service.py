from __future__ import annotations

import asyncio
import json
import logging
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..domain import Game, PlayerType
from ..engine import GameEngine
from .agent import AIAgent
from .config import AISettings
from .providers import (
    ProviderError,
    TypeSafeDecisionProvider,
    build_failover_provider,
)
from .runner import HeadlessGameRunner, HumanInputRequired, RunnerEntry


AUDIT_DIRECTORY = Path(__file__).resolve().parents[2] / ".game-audits"


def _write_audit_record(game_id: str, record: dict[str, Any]) -> None:
    AUDIT_DIRECTORY.mkdir(exist_ok=True)
    path = AUDIT_DIRECTORY / f"{game_id}.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")


def record_audit(game_id: str, record: dict[str, Any]) -> None:
    """Diagnostics must never turn an accepted game action into a failed action."""
    try:
        _write_audit_record(game_id, record)
    except OSError:
        logging.getLogger(__name__).warning("Audit storage unavailable for %s", game_id)


class OfflineProvider:
    provider_name = "offline"
    model = "deterministic-fallback"

    async def generate_json(self, **_):
        raise ProviderError("Offline simulation uses validated fallback decisions")


@dataclass(slots=True)
class AIRun:
    game_id: str
    mode: str
    status: str = "QUEUED"
    started_at: str | None = None
    finished_at: str | None = None
    current_step: int = 0
    last_progress_at: str | None = None
    last_action: dict[str, Any] | None = None
    summary: dict[str, Any] | None = None
    error: str | None = None
    human_player_id: str | None = None
    human_token: str | None = field(default=None, repr=False)
    control_token: str = field(default_factory=lambda: secrets.token_urlsafe(32), repr=False)
    character_id: int | None = None
    language: str = "fa"
    ai_model: str | None = None
    awaiting_actions: list[str] = field(default_factory=list)
    fallback_actions: int = 0
    last_failure: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    owner: str = "local"
    live_action_budget: int = 20
    receipts: dict[str, Any] = field(default_factory=dict, repr=False)
    credential_mode: str = "server"
    checkpoint: Any = field(default=None, repr=False)
    suspending: bool = False
    task: Any = field(default=None, repr=False)
    runner: Any = field(default=None, repr=False)
    drive_lock: Any = field(default=None, repr=False)

    def public_dict(self, *, participant: bool = False) -> dict[str, Any]:
        return {
            **({"accepted_request_ids": list(self.receipts)} if participant else {}),
            "game_id": self.game_id,
            "mode": self.mode,
            # Even a public "waiting for human" during Night 1 identifies the
            # human as Boss. Only that authenticated participant sees the wait.
            "status": "RUNNING" if self.status == "WAITING_FOR_HUMAN" and not participant else self.status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "current_step": self.current_step,
            # Action identities and diagnostic failures can reveal hidden roles.
            # Keep the detailed transcript server-side, even after game over.
            "summary": {
                key: self.summary[key]
                for key in ("winner", "rounds", "actions", "fallback_actions", "recovered_rule_errors")
                if key in self.summary
            } if self.summary is not None else None,
            "error": self.error,
            "human_player_id": self.human_player_id,
            "character_id": self.character_id,
            "language": self.language,
            "ai_model": self.ai_model,
            "fallback_actions": self.fallback_actions,
            "agent_health": "DEGRADED" if self.fallback_actions else "HEALTHY",
            **({
                "credential_required": self.mode == "live" and self.credential_mode == "participant"
                and self.status in {"QUEUED", "RUNNING"},
            } if participant else {}),
        }


class AIRunRegistry:
    def __init__(self) -> None:
        self._runs: dict[str, AIRun] = {}

    def add(self, run: AIRun) -> None:
        self._runs[run.game_id] = run

    def contains(self, game_id: str) -> bool:
        return game_id in self._runs

    def get(self, game_id: str) -> AIRun:
        try:
            return self._runs[game_id]
        except KeyError as exc:
            from ..domain import RuleViolation

            raise RuleViolation("AI_RUN_NOT_FOUND") from exc


def build_runner(
    engine: GameEngine,
    game: Game,
    *,
    mode: str,
    settings: AISettings | None,
    live_action_budget: int | None,
    language: str = "fa",
    player_names: dict[str, str] | None = None,
    on_entry=None,
    allow_fallback: bool = True,
) -> HeadlessGameRunner:
    gate = None
    if mode == "live" and settings and settings.typesafe:
        gate = TypeSafeDecisionProvider(
            settings.typesafe,
            timeout_seconds=settings.request_timeout_seconds,
            min_interval_seconds=settings.min_request_interval_seconds,
        )
    agents: dict[str, AIAgent] = {}
    ai_players = [
        player_id
        for player_id, player in game.players.items()
        if player.player_type == PlayerType.AI
    ]
    for index, player_id in enumerate(ai_players):
        if mode == "live":
            if settings is None:
                raise ValueError("Live mode requires AI settings")
            provider = build_failover_provider(
                settings.player_providers[index],
                (),
                timeout_seconds=settings.request_timeout_seconds,
                min_interval_seconds=settings.min_request_interval_seconds,
                reasoning_effort=settings.openai_reasoning_effort,
            )
            agents[player_id] = AIAgent(
                player_id,
                provider,
                require_assessment=False,
                max_output_tokens=min(settings.max_output_tokens, 4096),
                speak_max_output_tokens=min(settings.speak_max_output_tokens, 4096),
                decision_gate=gate,
                decision_timeout_seconds=min(settings.decision_timeout_seconds, 60),
                gate_timeout_seconds=min(settings.typesafe_decision_timeout_seconds, 30),
                remote_decision_budget=live_action_budget,
                gate_decision_budget=live_action_budget,
                language=language,
                player_names=player_names,
                allow_fallback=allow_fallback,
            )
        else:
            agents[player_id] = AIAgent(
                player_id,
                OfflineProvider(),
                language=language,
                player_names=player_names,
            )
    return HeadlessGameRunner(engine, game, agents, on_entry=on_entry)


async def execute_run(
    run: AIRun,
    runner: HeadlessGameRunner,
    *,
    batch_steps: int | None = None,
    propagate_errors: bool = False,
) -> None:
    run.status = "RUNNING"
    run.awaiting_actions.clear()
    if run.started_at is None:
        run.started_at = datetime.now(UTC).isoformat()
    try:
        async with asyncio.timeout(900):
            await runner.run(batch_steps=batch_steps, continue_if=lambda: run.status == "RUNNING")
        if runner.game.phase.value != "GAME_OVER":
            run.status = "QUEUED"
            return
        run.summary = runner.summary()
        run.status = "COMPLETED"
        run.finished_at = datetime.now(UTC).isoformat()
        record_audit(run.game_id, {"type": "RUN_COMPLETED", "summary": run.summary})
        record_audit(run.game_id, {
            "type": "COMPLETED_NIGHT_REPLAY",
            "nights": runner.engine.completed_night_replay(runner.game),
        })
    except HumanInputRequired as exc:
        run.status = "WAITING_FOR_HUMAN"
        run.awaiting_actions = runner.required_actions(exc.player_id)
    except asyncio.CancelledError:
        if run.suspending:
            run.status = "QUEUED"
            return
        run.status = "CANCELLED"
        run.finished_at = datetime.now(UTC).isoformat()
        record_audit(run.game_id, {"type": "RUN_CANCELLED"})
    except Exception as exc:
        if propagate_errors:
            raise
        run.status = "FAILED"
        run.error = type(exc).__name__
        run.finished_at = datetime.now(UTC).isoformat()
        record_audit(
            run.game_id,
            {"type": "RUN_FAILED", "error": type(exc).__name__, "message": str(exc)[:500]},
        )

    finally:
        if run.checkpoint:
            run.checkpoint()


def update_run_progress(run: AIRun, entry: RunnerEntry, *, audit: bool = True) -> None:
    run.current_step = entry.step
    run.last_progress_at = datetime.now(UTC).isoformat()
    run.last_action = {
        "round": entry.round,
        "phase": entry.phase,
        "player_id": entry.player_id,
        "action": entry.action,
        "source": entry.source,
    }
    if entry.source.startswith("fallback"):
        run.fallback_actions += 1
    if entry.failure:
        run.last_failure = entry.failure
    if audit:
        audit_entry(run, entry)


def audit_entry(run: AIRun, entry: RunnerEntry) -> None:
    record_audit(
        run.game_id,
        {
            "type": "DECISION",
            "step": entry.step,
            "round": entry.round,
            "phase": entry.phase,
            "player_id": entry.player_id,
            "action": entry.action,
            "source": entry.source,
            "failure": entry.failure,
            "recovered_from_error": entry.recovered_from_error,
            "corrections": list(entry.corrections),
        },
    )
