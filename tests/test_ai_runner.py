from __future__ import annotations

import pytest

from app.ai.agent import AIAgent
from app.ai.providers import ProviderError
from app.ai.runner import HeadlessGameRunner
from app.domain import Faction, Phase, PlayerType
from app.engine import GameEngine


class OfflineProvider:
    provider_name = "offline"
    model = "offline"

    async def generate_json(self, **_):
        raise ProviderError("offline by design")


@pytest.mark.anyio
async def test_seven_agent_headless_game_finishes_using_filtered_views():
    engine = GameEngine()
    game = engine.create_game([PlayerType.AI] * 7, seed=5)
    agents = {
        player_id: AIAgent(player_id, OfflineProvider()) for player_id in game.players
    }
    runner = HeadlessGameRunner(engine, game, agents)
    result = await runner.run(max_steps=150)

    assert result.phase == Phase.GAME_OVER
    assert result.winner in {Faction.MAFIA, Faction.CITIZEN}
    assert runner.transcript
    assert all(entry.source == "fallback" for entry in runner.transcript)
    assert all(agent.state.memory for agent in agents.values())
    assert not any("token" in memory.summary for agent in agents.values() for memory in agent.state.memory)
