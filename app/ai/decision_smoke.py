from __future__ import annotations

import argparse
import asyncio
import json

from ..domain import Phase, PlayerType
from ..engine import GameEngine
from .agent import AIAgent, Observation
from .config import AISettings
from .providers import build_provider


async def run(provider_name: str, env_file: str) -> dict:
    settings = AISettings.from_environment(env_file=env_file)
    config = next(
        item for item in settings.player_providers if item.provider == provider_name
    )
    engine = GameEngine()
    game = engine.create_game([PlayerType.AI] * 7, seed=19)
    game.phase = Phase.ROLE_CLAIM
    player_id = "P1"
    provider = build_provider(
        config,
        timeout_seconds=settings.request_timeout_seconds,
        min_interval_seconds=0,
        reasoning_effort=settings.openai_reasoning_effort,
    )
    agent = AIAgent(
        player_id,
        provider,
        max_output_tokens=settings.max_output_tokens,
        speak_max_output_tokens=settings.speak_max_output_tokens,
        decision_timeout_seconds=settings.decision_timeout_seconds,
    )
    observation = Observation(
        player_id=player_id,
        public_state=engine.public_state(game),
        private_state=engine.private_state(game, player_id),
        available_actions=["ROLE_CLAIM"],
        events=engine.visible_events(game, player_id),
    )
    decision = await agent.decide(observation)
    return {
        "provider": config.provider,
        "model": config.model,
        "source": decision.source,
        "action": decision.action,
        "failure": agent.last_failure,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Test one full Palermo decision contract")
    parser.add_argument("--only", choices=["gemini", "hetzner"], required=True)
    parser.add_argument("--env-file", default=".env")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(args.only, args.env_file)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
