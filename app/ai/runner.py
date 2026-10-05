from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from ..domain import Action, Game, Phase, PlayerType, RuleViolation
from ..engine import GameEngine
from .agent import AIAgent, AgentDecision, Observation
from .reasoning import checked_decision


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
    failure: str | None = None
    recovered_from_error: str | None = None
    corrections: tuple[str, ...] = ()


@dataclass(slots=True)
class HeadlessGameRunner:
    engine: GameEngine
    game: Game
    agents: dict[str, AIAgent]
    transcript: list[RunnerEntry] = field(default_factory=list)
    on_entry: Callable[[RunnerEntry], None] | None = None

    async def run(self, *, max_steps: int = 300, batch_steps: int | None = None, continue_if=None) -> Game:
        initial = len(self.transcript)
        for step in range(initial + 1, max_steps + 1):
            if self.game.phase == Phase.GAME_OVER:
                return self.game
            player_id, actions = self._next_actor()
            player = self.game.players[player_id]
            if player.player_type == PlayerType.HUMAN:
                raise HumanInputRequired(player_id)
            agent = self.agents.get(player_id)
            if agent is None:
                raise RuntimeError(f"No AI agent registered for {player_id}")
            observation = self.observation(player_id, actions)
            action_round = self.game.round
            action_phase = self.game.phase.value
            decision = await agent.decide(observation)
            if continue_if is not None and not continue_if():
                import asyncio
                raise asyncio.CancelledError
            recovered = None
            try:
                self.submit_decision(player_id, decision.action, dict(decision.payload), actions)
            except RuleViolation as exc:
                recovered = exc.code
                decision = checked_decision(agent, agent.fallback_decision(observation), {}, observation)
                self.submit_decision(player_id, decision.action, dict(decision.payload), actions)
            entry = RunnerEntry(
                step=step,
                round=action_round,
                phase=action_phase,
                player_id=player_id,
                action=decision.action,
                source=decision.source,
                failure=agent.last_failure,
                recovered_from_error=recovered,
                corrections=decision.corrections,
            )
            self.transcript.append(entry)
            if self.on_entry:
                self.on_entry(entry)
            if batch_steps and step - initial >= batch_steps:
                return self.game
        raise RunnerLimitExceeded(f"Game did not finish within {max_steps} actions")

    async def step(self) -> AgentDecision:
        if self.game.phase == Phase.GAME_OVER:
            raise RuntimeError("Game is already over")
        player_id, actions = self._next_actor()
        if self.game.players[player_id].player_type == PlayerType.HUMAN:
            raise HumanInputRequired(player_id)
        observation = self.observation(player_id, actions)
        decision = await self.agents[player_id].decide(observation)
        self.submit_decision(player_id, decision.action, dict(decision.payload), actions)
        return decision

    def submit_decision(
        self,
        player_id: str,
        action: str,
        payload: dict[str, Any],
        required_actions: list[str] | None = None,
    ) -> dict[str, Any]:
        """Single action gateway shared by human and AI participants."""
        legal = required_actions if required_actions is not None else self.required_actions(player_id)
        if action not in legal:
            raise RuleViolation("ACTION_NOT_AVAILABLE_IN_CURRENT_STATE")
        return self.engine.submit_action(self.game, player_id, action, payload)

    def submit_participant_decision(
        self,
        player_id: str,
        action: str,
        payload: dict[str, Any],
        *,
        source: str,
        required_actions: list[str] | None = None,
        failure: str | None = None,
    ) -> dict[str, Any]:
        """Submit and audit a decision through the shared participant gateway."""
        action_round = self.game.round
        action_phase = self.game.phase.value
        result = self.submit_decision(player_id, action, payload, required_actions)
        entry = RunnerEntry(
            step=len(self.transcript) + 1,
            round=action_round,
            phase=action_phase,
            player_id=player_id,
            action=action,
            source=source,
            failure=failure,
        )
        self.transcript.append(entry)
        if self.on_entry:
            self.on_entry(entry)
        return result

    def _next_actor(self) -> tuple[str, list[str]]:
        for player_id, player in self.game.players.items():
            if not player.alive:
                continue
            actions = self._required_actions(player_id)
            if actions:
                return player_id, actions
        raise RuntimeError(f"No actor can advance phase {self.game.phase.value}")

    def required_actions(self, player_id: str) -> list[str]:
        """Return only actions that advance the current turn."""
        return list(self._required_actions(player_id))

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

    def observation(
        self, player_id: str, actions: list[str] | None = None
    ) -> Observation:
        # This is the information-filter boundary. No Player/Game object is ever
        # passed to an agent; it receives only the same views exposed by the API.
        legal_actions = self.required_actions(player_id) if actions is None else actions
        return Observation(
            player_id=player_id,
            public_state=self.engine.public_state(self.game),
            private_state=self.engine.private_state(self.game, player_id),
            available_actions=list(legal_actions),
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
            "fallback_actions_by_type": {
                action: sum(
                    entry.action == action and entry.source.startswith("fallback")
                    for entry in self.transcript
                )
                for action in sorted({entry.action for entry in self.transcript})
            },
            "failures": [
                {
                    "step": entry.step,
                    "player_id": entry.player_id,
                    "action": entry.action,
                    "failure": entry.failure,
                }
                for entry in self.transcript
                if entry.failure
            ],
            "recovered_rule_errors": sum(
                entry.recovered_from_error is not None for entry in self.transcript
            ),
            "repaired_model_actions": sum(bool(entry.corrections) for entry in self.transcript),
        }
