from __future__ import annotations

import pytest

from app.ai.agent import AIAgent, Observation
from app.ai.providers import ProviderError
from app.ai.runner import HeadlessGameRunner
from app.domain import Faction, Phase, PlayerType
from app.engine import GameEngine


class OfflineProvider:
    provider_name = "offline"
    model = "offline"

    async def generate_json(self, **_):
        raise ProviderError("offline by design")


class StaticProvider:
    provider_name = "static"
    model = "static"

    def __init__(self, result):
        self.result = result

    async def generate_json(self, **_):
        return self.result


def test_discussion_schema_caps_visible_agent_text() -> None:
    agent = AIAgent("P2", OfflineProvider())
    observation = Observation(
        player_id="P2",
        public_state={"alive_players": ["P1", "P2"], "players": {}},
        private_state={},
        available_actions=["SPEAK", "PASS"],
        events=[],
    )

    schema = agent._decision_schema(observation)

    assert schema["properties"]["text"]["maxLength"] == 500


def test_agent_role_claim_schema_allows_only_public_claim_roles() -> None:
    agent = AIAgent("P2", OfflineProvider())
    observation = Observation(
        player_id="P2",
        public_state={"alive_players": ["P1", "P2"], "players": {}},
        private_state={},
        available_actions=["ROLE_CLAIM"],
        events=[],
    )

    schema = agent._decision_schema(observation)

    assert set(schema["properties"]["claimed_role"]["enum"]) == {
        "CITIZEN", "DOCTOR", "DETECTIVE"
    }


def test_answer_schema_is_one_batch_without_question_selection() -> None:
    agent = AIAgent("P2", OfflineProvider())
    observation = Observation(
        player_id="P2",
        public_state={
            "alive_players": ["P1", "P2", "P3"],
            "players": {pid: {"alive": True, "shunned": False} for pid in ("P1", "P2", "P3")},
        },
        private_state={},
        available_actions=["ANSWER"],
        events=[
            {"type": "PLAYER_ASKED", "question_id": "q_1_1", "actor": "P1", "target": "P2"},
            {"type": "PLAYER_ASKED", "question_id": "q_1_2", "actor": "P3", "target": "P2"},
        ],
    )

    schema = agent._decision_schema(observation)

    assert "question_id" not in schema["properties"]
    assert schema["properties"]["text"]["maxLength"] == 1200


def test_vote_fallback_uses_evidence_instead_of_first_player_order() -> None:
    agent = AIAgent("P4", OfflineProvider())
    observation = Observation(
        player_id="P4",
        public_state={
            "game_id": "game_replay",
            "round": 3,
            "alive_players": ["P1", "P3", "P4", "P5", "P6", "P7"],
            "players": {pid: {"shunned": False} for pid in ["P1", "P3", "P4", "P5", "P6", "P7"]},
            "role_claims": {"P7": "DOCTOR"},
            "revealed_roles": {"P2": "DOCTOR"},
        },
        private_state={"trust": {pid: 50 for pid in ["P1", "P3", "P5", "P6", "P7"]}},
        available_actions=["SUBMIT_VOTE_DECISION"],
        events=[],
    )

    decision = agent.fallback_decision(observation)

    assert decision.payload["vote_target"] == "P7"
    assert decision.payload["vote_target"] != observation.public_state["alive_players"][0]
    assert len({decision.payload["vote_target"], decision.payload["trusted_player"], decision.payload["suspect_2"]}) == 3


@pytest.mark.anyio
async def test_agent_dialogue_uses_structured_player_references() -> None:
    provider = StaticProvider({
        "action": "SPEAK",
        "target": None,
        "text": "از {{P1}} می‌خواهم ادعایش را توضیح دهد.",
        "referenced_players": ["P1"],
        "reasoning_summary": "clarify claim",
    })
    names = {"P1": "Marco Conti", "P2": "Matteo Ricci"}
    agent = AIAgent("P2", provider, player_names=names)
    observation = Observation(
        player_id="P2",
        public_state={
            "game_id": "game_names", "round": 1,
            "alive_players": ["P1", "P2"],
            "players": {"P1": {"alive": True, "shunned": False}, "P2": {"alive": True, "shunned": False}},
            "role_claims": {"P1": "CITIZEN", "P2": "DOCTOR"},
            "revealed_roles": {},
        },
        private_state={"trust": {"P1": 50}},
        available_actions=["SPEAK", "ASK", "PASS"],
        events=[],
    )

    decision = await agent.decide(observation)

    assert decision.source == "model"
    assert decision.payload["text"] == "از Marco Conti می‌خواهم ادعایش را توضیح دهد."
    assert "P1" not in decision.payload["text"]


@pytest.mark.anyio
async def test_agent_converts_targeted_question_from_speak_to_ask() -> None:
    provider = StaticProvider({
        "action": "SPEAK",
        "target": None,
        "text": "{{P1}}، چرا دیشب نتیجه‌ای نداشتی؟",
        "referenced_players": ["P1"],
        "reasoning_summary": "request an answer",
    })
    agent = AIAgent(
        "P2", provider, player_names={"P1": "Luca Romano", "P2": "Matteo Ricci"}
    )
    observation = Observation(
        player_id="P2",
        public_state={
            "game_id": "game_question", "round": 2,
            "alive_players": ["P1", "P2"],
            "players": {
                "P1": {"alive": True, "shunned": False},
                "P2": {"alive": True, "shunned": False},
            },
            "role_claims": {"P1": "DETECTIVE", "P2": "CITIZEN"},
            "revealed_roles": {},
        },
        private_state={"trust": {"P1": 50}},
        available_actions=["SPEAK", "ASK", "PASS"],
        events=[],
    )

    decision = await agent.decide(observation)

    assert decision.source == "model"
    assert decision.action == "ASK"
    assert decision.payload["target"] == "P1"
    assert decision.payload["text"].startswith("Luca Romano")


@pytest.mark.anyio
async def test_dialogue_allows_unused_but_known_structured_references() -> None:
    provider = StaticProvider({
        "action": "SPEAK",
        "target": None,
        "text": "رأی {{P1}} را مشکوک می‌دانم.",
        "referenced_players": ["P1", "P3"],
        "reasoning_summary": "compare votes",
    })
    names = {"P1": "Luca Romano", "P2": "Matteo Ricci", "P3": "Rosa Greco"}
    agent = AIAgent("P2", provider, player_names=names)
    observation = Observation(
        player_id="P2",
        public_state={
            "game_id": "game_refs", "round": 2,
            "alive_players": ["P1", "P2", "P3"],
            "players": {
                pid: {"alive": True, "shunned": False} for pid in names
            },
            "role_claims": {},
            "revealed_roles": {},
        },
        private_state={"trust": {"P1": 50, "P3": 50}},
        available_actions=["SPEAK", "ASK", "PASS"],
        events=[],
    )

    decision = await agent.decide(observation)

    assert decision.source == "model"
    assert decision.action == "SPEAK"
    assert decision.payload["text"] == "رأی Luca Romano را مشکوک می‌دانم."


def test_human_and_ai_share_the_same_runner_gateway() -> None:
    engine = GameEngine()
    game = engine.create_game([PlayerType.HUMAN, *([PlayerType.AI] * 6)], seed=12)
    game.phase = Phase.ROLE_CLAIM
    runner = HeadlessGameRunner(engine, game, {})

    runner.submit_participant_decision(
        "P1", "ROLE_CLAIM", {"claimed_role": "CITIZEN"}, source="human"
    )

    assert game.players["P1"].role_claim.value == "CITIZEN"
    assert runner.transcript[-1].source == "human"
    assert runner.observation("P1").public_state == engine.public_state(game)


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
