from __future__ import annotations

import argparse
import asyncio
import json
import sys

from .ai.config import AISettings
from .ai.service import build_runner
from .domain import PlayerType
from .engine import GameEngine


async def simulate(
    *, live: bool, seed: int, env_file: str, live_action_budget: int | None = None
) -> dict:
    engine = GameEngine()
    game = engine.create_game([PlayerType.AI] * 7, seed=seed)
    settings = AISettings.from_environment(env_file=env_file) if live else None
    def progress(entry):
        print(
            f"step={entry.step} round={entry.round} phase={entry.phase} "
            f"player={entry.player_id} action={entry.action} source={entry.source}",
            file=sys.stderr,
            flush=True,
        )

    runner = build_runner(
        engine,
        game,
        mode="live" if live else "offline",
        settings=settings,
        live_action_budget=live_action_budget,
        on_entry=progress if live else None,
    )
    await runner.run()
    result = runner.summary()
    result["mode"] = "live" if live else "offline"
    result["providers"] = {
        player_id: f"{agent.provider.provider_name}:{agent.provider.model}"
        for player_id, agent in runner.agents.items()
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
