from __future__ import annotations

import argparse
import asyncio
import json

from ..domain import Phase, PlayerType
from ..engine import GameEngine
from .agent import AIAgent, Observation
from .config import AISettings
from .providers import build_provider


async def run(provider_name: str, env_file: str, action: str = "ROLE_CLAIM") -> dict:
    settings = (
        AISettings.for_openai_players(player_count=1, env_file=env_file)
        if provider_name == "openai"
        else AISettings.from_environment(env_file=env_file)
    )
    config = next(item for item in settings.player_providers if item.provider == provider_name)
    engine = GameEngine()
    game = engine.create_game([PlayerType.AI] * 7, seed=19)
    game.phase = {
        "ROLE_CLAIM": Phase.ROLE_CLAIM,
        "VOTE": Phase.DAY_VOTING,
        "SPEAK": Phase.DAY_DISCUSSION,
    }[action]
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
        language="fa",
        player_names={f"P{index}": f"Player {index}" for index in range(1, 8)},
    )
    observation = Observation(
        player_id=player_id,
        public_state=engine.public_state(game),
        private_state=engine.private_state(game, player_id),
        available_actions={
            "ROLE_CLAIM": ["ROLE_CLAIM"],
            "VOTE": ["SUBMIT_VOTE_DECISION"],
            "SPEAK": ["SPEAK", "ASK", "PASS"],
        }[action],
        events=engine.visible_events(game, player_id),
    )
    decision = await agent.decide(observation)
    return {
        "provider": config.provider,
        "model": config.model,
        "source": decision.source,
        "action": decision.action,
        "failure": agent.last_failure,
        "payload": decision.payload,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Test one full Palermo decision contract")
    parser.add_argument("--only", choices=["gemini", "hetzner", "openai"], required=True)
    parser.add_argument("--action", choices=["ROLE_CLAIM", "VOTE", "SPEAK"], default="ROLE_CLAIM")
    parser.add_argument("--env-file", default=".env")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(args.only, args.env_file, args.action)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
