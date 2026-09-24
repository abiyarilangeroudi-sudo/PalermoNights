from __future__ import annotations

import argparse
import asyncio
import json
import sys

from .ai.agent import AIAgent
from .ai.config import AISettings
from .ai.providers import (
    ProviderError,
    TypeSafeDecisionProvider,
    build_failover_provider,
)
from .ai.runner import HeadlessGameRunner
from .domain import PlayerType
from .engine import GameEngine


class OfflineProvider:
    provider_name = "offline"
    model = "deterministic-fallback"

    async def generate_json(self, **_):
        raise ProviderError("Offline simulation uses validated fallback decisions")


async def simulate(
    *, live: bool, seed: int, env_file: str, live_action_budget: int | None = None
) -> dict:
    engine = GameEngine()
    game = engine.create_game([PlayerType.AI] * 7, seed=seed)
    settings = AISettings.from_environment(env_file=env_file) if live else None
    gate = None
    if settings and settings.typesafe:
        gate = TypeSafeDecisionProvider(
            settings.typesafe,
            timeout_seconds=settings.request_timeout_seconds,
            min_interval_seconds=settings.min_request_interval_seconds,
        )
    agents = {}
    for index, player_id in enumerate(game.players):
        if settings:
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
    def progress(entry):
        print(
            f"step={entry.step} round={entry.round} phase={entry.phase} "
            f"player={entry.player_id} action={entry.action} source={entry.source}",
            file=sys.stderr,
            flush=True,
        )

    runner = HeadlessGameRunner(engine, game, agents, on_entry=progress if live else None)
    await runner.run()
    result = runner.summary()
    result["mode"] = "live" if live else "offline"
    result["providers"] = {
        player_id: f"{agent.provider.provider_name}:{agent.provider.model}"
        for player_id, agent in agents.items()
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a seven-agent Palermo Nights match")
    parser.add_argument("--live", action="store_true", help="Use configured remote AI providers")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--env-file", default=".env")
    parser.add_argument(
        "--live-action-budget",
        type=int,
        default=1,
        help="Remote model/gate calls per agent; 0 means unlimited (default: 1)",
    )
    args = parser.parse_args()
    budget = None if args.live_action_budget == 0 else args.live_action_budget
    result = asyncio.run(
        simulate(
            live=args.live,
            seed=args.seed,
            env_file=args.env_file,
            live_action_budget=budget,
        )
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
