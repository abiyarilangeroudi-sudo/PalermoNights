from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from ..domain import Action, Game, Phase, PlayerType, RuleViolation
from ..engine import GameEngine
from .agent import AIAgent, AgentDecision, Observation


class HumanInputRequired(RuntimeError):
    def __init__(self, player_id: str):
        self.player_id = player_id
        super().__init__(f"Human input is required for {player_id}")


class RunnerLimitExceeded(RuntimeError):
    pass


@dataclass(slots=True)
class RunnerEntry:
    step: int
    round: int
    phase: str
    player_id: str
    action: str
    source: str
    recovered_from_error: str | None = None


@dataclass(slots=True)
class HeadlessGameRunner:
    engine: GameEngine
    game: Game
    agents: dict[str, AIAgent]
    transcript: list[RunnerEntry] = field(default_factory=list)
    on_entry: Callable[[RunnerEntry], None] | None = None

    async def run(self, *, max_steps: int = 300) -> Game:
        for step in range(1, max_steps + 1):
            if self.game.phase == Phase.GAME_OVER:
                return self.game
            player_id, actions = self._next_actor()
            player = self.game.players[player_id]
            if player.player_type == PlayerType.HUMAN:
                raise HumanInputRequired(player_id)
            agent = self.agents.get(player_id)
            if agent is None:
                raise RuntimeError(f"No AI agent registered for {player_id}")
            observation = self._observation(player_id, actions)
            action_round = self.game.round
            action_phase = self.game.phase.value
            decision = await agent.decide(observation)
            recovered = None
            try:
                self.engine.submit_action(
                    self.game, player_id, decision.action, dict(decision.payload)
                )
            except RuleViolation as exc:
                recovered = exc.code
                decision = agent.fallback_decision(observation)
                self.engine.submit_action(
                    self.game, player_id, decision.action, dict(decision.payload)
                )
            entry = RunnerEntry(
                    step=step,
                    round=action_round,
                    phase=action_phase,
                    player_id=player_id,
                    action=decision.action,
                    source=decision.source,
                    recovered_from_error=recovered,
                )
            self.transcript.append(entry)
            if self.on_entry:
                self.on_entry(entry)
        raise RunnerLimitExceeded(f"Game did not finish within {max_steps} actions")

    async def step(self) -> AgentDecision:
        if self.game.phase == Phase.GAME_OVER:
            raise RuntimeError("Game is already over")
        player_id, actions = self._next_actor()
        if self.game.players[player_id].player_type == PlayerType.HUMAN:
            raise HumanInputRequired(player_id)
        observation = self._observation(player_id, actions)
        decision = await self.agents[player_id].decide(observation)
        self.engine.submit_action(self.game, player_id, decision.action, dict(decision.payload))
        return decision

    def _next_actor(self) -> tuple[str, list[str]]:
        for player_id, player in self.game.players.items():
            if not player.alive:
                continue
            actions = self._required_actions(player_id)
            if actions:
                return player_id, actions
        raise RuntimeError(f"No actor can advance phase {self.game.phase.value}")

    def _required_actions(self, player_id: str) -> list[str]:
        actions = [
            action
            for action in self.engine.available_actions(self.game, player_id)
            if action != Action.SET_WILL.value
        ]
        if self.game.phase == Phase.DAY_DISCUSSION:
            if Action.ANSWER.value in actions:
                return [Action.ANSWER.value]
            speaking = [
                action
                for action in actions
                if action in {Action.SPEAK.value, Action.ASK.value, Action.PASS.value}
            ]
            return speaking
        return actions

    def _observation(self, player_id: str, actions: list[str]) -> Observation:
        # This is the information-filter boundary. No Player/Game object is ever
        # passed to an agent; it receives only the same views exposed by the API.
        return Observation(
            player_id=player_id,
            public_state=self.engine.public_state(self.game),
            private_state=self.engine.private_state(self.game, player_id),
            available_actions=list(actions),
            events=self.engine.visible_events(self.game, player_id),
        )

    def summary(self) -> dict[str, Any]:
        return {
            "game_id": self.game.game_id,
            "winner": self.game.winner.value if self.game.winner else None,
            "rounds": self.game.round,
            "actions": len(self.transcript),
            "fallback_actions": sum(
                entry.source.startswith("fallback") for entry in self.transcript
            ),
            "recovered_rule_errors": sum(
                entry.recovered_from_error is not None for entry in self.transcript
            ),
        }
