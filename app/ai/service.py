from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from ..domain import Game
from ..engine import GameEngine
from .agent import AIAgent
from .config import AISettings
from .providers import (
    ProviderError,
    TypeSafeDecisionProvider,
    build_failover_provider,
)
from .runner import HeadlessGameRunner, RunnerEntry


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
    last_action: dict[str, Any] | None = None
    summary: dict[str, Any] | None = None
    error: str | None = None
    task: Any = field(default=None, repr=False)

    def public_dict(self) -> dict[str, Any]:
        return {
            "game_id": self.game_id,
            "mode": self.mode,
            "status": self.status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "current_step": self.current_step,
            "last_action": self.last_action,
            "summary": self.summary,
            "error": self.error,
        }


class AIRunRegistry:
    def __init__(self) -> None:
        self._runs: dict[str, AIRun] = {}

    def add(self, run: AIRun) -> None:
        self._runs[run.game_id] = run

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
    on_entry=None,
) -> HeadlessGameRunner:
    gate = None
    if mode == "live" and settings and settings.typesafe:
        gate = TypeSafeDecisionProvider(
            settings.typesafe,
            timeout_seconds=settings.request_timeout_seconds,
            min_interval_seconds=settings.min_request_interval_seconds,
        )
    agents: dict[str, AIAgent] = {}
    for index, player_id in enumerate(game.players):
        if mode == "live":
            if settings is None:
                raise ValueError("Live mode requires AI settings")
            provider = build_failover_provider(
                settings.player_providers[index],
                settings.fallback_providers,
                timeout_seconds=settings.request_timeout_seconds,
                min_interval_seconds=settings.min_request_interval_seconds,
                reasoning_effort=settings.openai_reasoning_effort,
            )
            agents[player_id] = AIAgent(
                player_id,
                provider,
                max_output_tokens=settings.max_output_tokens,
                speak_max_output_tokens=settings.speak_max_output_tokens,
                decision_gate=gate,
                decision_timeout_seconds=settings.decision_timeout_seconds,
                gate_timeout_seconds=settings.typesafe_decision_timeout_seconds,
                remote_decision_budget=live_action_budget,
                gate_decision_budget=live_action_budget,
            )
        else:
            agents[player_id] = AIAgent(player_id, OfflineProvider())
    return HeadlessGameRunner(engine, game, agents, on_entry=on_entry)


async def execute_run(run: AIRun, runner: HeadlessGameRunner) -> None:
    run.status = "RUNNING"
    run.started_at = datetime.now(UTC).isoformat()
    try:
        await runner.run()
        run.summary = runner.summary()
        run.status = "COMPLETED"
    except asyncio.CancelledError:
        run.status = "CANCELLED"
    except Exception as exc:
        run.status = "FAILED"
        run.error = type(exc).__name__
    finally:
        run.finished_at = datetime.now(UTC).isoformat()


def update_run_progress(run: AIRun, entry: RunnerEntry) -> None:
    run.current_step = entry.step
    run.last_action = {
        "round": entry.round,
        "phase": entry.phase,
        "player_id": entry.player_id,
        "action": entry.action,
        "source": entry.source,
    }
