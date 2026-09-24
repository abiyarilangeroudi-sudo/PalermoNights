from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

from ..domain import Action, Role
from .providers import JsonProvider, ProviderError, TypeSafeDecisionProvider


@dataclass(slots=True)
class Observation:
    player_id: str
    public_state: dict[str, Any]
    private_state: dict[str, Any]
    available_actions: list[str]
    events: list[dict[str, Any]]


@dataclass(slots=True)
class AgentMemory:
    event_id: str
    summary: str
    round: int
    importance: float


@dataclass(slots=True)
class AgentState:
    memory: list[AgentMemory] = field(default_factory=list)
    beliefs: dict[str, float] = field(default_factory=dict)
    hypotheses: list[str] = field(default_factory=list)
    strategy: str | None = None
    seen_event_ids: set[str] = field(default_factory=set)


@dataclass(frozen=True, slots=True)
class AgentDecision:
    action: str
    payload: dict[str, Any]
    source: str = "model"


DECISION_FIELDS = (
    "target", "text", "claimed_role", "strategy", "vote_target",
    "suspect_2", "trusted_player", "question_id"
)


class AIAgent:
    def __init__(
        self,
        player_id: str,
        provider: JsonProvider,
        *,
        max_output_tokens: int = 180,
        speak_max_output_tokens: int = 512,
        decision_gate: TypeSafeDecisionProvider | None = None,
        decision_timeout_seconds: float = 45.0,
        gate_timeout_seconds: float = 15.0,
        remote_decision_budget: int | None = None,
        gate_decision_budget: int | None = None,
    ) -> None:
        self.player_id = player_id
        self.provider = provider
        self.max_output_tokens = max_output_tokens
        self.speak_max_output_tokens = speak_max_output_tokens
        self.decision_gate = decision_gate
        self.decision_timeout_seconds = decision_timeout_seconds
        self.gate_timeout_seconds = gate_timeout_seconds
        self.remote_decision_budget = remote_decision_budget
        self.gate_decision_budget = gate_decision_budget
        self.remote_decisions_used = 0
        self.gate_decisions_used = 0
        self.last_failure: str | None = None
        self.state = AgentState()

    async def decide(self, observation: Observation) -> AgentDecision:
        self._remember(observation.events)
        self._initialize_beliefs(observation)
        if (
            self.remote_decision_budget is not None
            and self.remote_decisions_used >= self.remote_decision_budget
        ):
            fallback = self.fallback_decision(observation)
            return await self._gate_target(fallback, observation)
        max_tokens = (
            self.speak_max_output_tokens
            if any(action in observation.available_actions for action in ("SPEAK", "ASK", "ANSWER"))
            else self.max_output_tokens
        )
        try:
            self.remote_decisions_used += 1
            schema = self._decision_schema(observation)
            async with asyncio.timeout(self.decision_timeout_seconds):
                result = await self.provider.generate_json(
                    system_prompt=self._system_prompt(),
                    user_prompt=self._user_prompt(observation),
                    schema=schema,
                    max_output_tokens=max_tokens,
                )
            decision = self._parse_decision(result, observation)
            decision = await self._gate_target(decision, observation)
            self._apply_agent_state(result, observation)
            self.last_failure = None
            return decision
        except (ProviderError, TimeoutError, ValueError, KeyError, TypeError) as exc:
            self.last_failure = self._safe_failure(exc)
            fallback = self.fallback_decision(observation)
            return await self._gate_target(fallback, observation)

    def fallback_decision(self, observation: Observation) -> AgentDecision:
        actions = set(observation.available_actions)
        public = observation.public_state
        private = observation.private_state
        alive = list(public["alive_players"])
        shunned = {pid for pid, data in public["players"].items() if data["shunned"]}
        others = [pid for pid in alive if pid != self.player_id]

        if Action.SELECT_STRATEGY.value in actions:
            return AgentDecision(
                Action.SELECT_STRATEGY.value,
                {"strategy": "USE_CONTRADICTION"},
                "fallback",
            )
        if Action.ROLE_CLAIM.value in actions:
            return AgentDecision(
                Action.ROLE_CLAIM.value,
                {"claimed_role": Role.CITIZEN.value},
                "fallback",
            )
        if Action.ANSWER.value in actions:
            pending = next(
                event
                for event in reversed(observation.events)
                if event.get("type") == "PLAYER_ASKED"
                and event.get("target") == self.player_id
                and not self._question_answered(observation.events, event["question_id"])
            )
            return AgentDecision(
                Action.ANSWER.value,
                {"question_id": pending["question_id"], "text": "رأی و ادعایم را بر اساس شواهد عمومی توضیح می‌دهم."},
                "fallback",
            )
        if Action.SPEAK.value in actions:
            return AgentDecision(
                Action.SPEAK.value,
                {"text": "فعلاً به تناقض ادعاها و الگوی رأی‌ها توجه می‌کنم."},
                "fallback",
            )
        if Action.PASS.value in actions:
            return AgentDecision(Action.PASS.value, {}, "fallback")
        if Action.SUBMIT_VOTE_DECISION.value in actions:
            vote_target = others[0]
            trusted = next(pid for pid in reversed(others) if pid != vote_target)
            payload: dict[str, Any] = {
                "vote_target": vote_target,
                "trusted_player": trusted,
            }
            revealed = public.get("revealed_roles", {}).values()
            alive_mafia = 2 - sum(
                role in {Role.MAFIA_BOSS.value, Role.MAFIA_DEPUTY.value} for role in revealed
            )
            if alive_mafia > 1:
                payload["suspect_2"] = next(
                    pid for pid in others if pid not in {vote_target, trusted}
                )
            return AgentDecision(Action.SUBMIT_VOTE_DECISION.value, payload, "fallback")
        if Action.INVESTIGATE.value in actions:
            target = next(pid for pid in others if pid not in shunned)
            return AgentDecision(Action.INVESTIGATE.value, {"target": target}, "fallback")
        if Action.PROTECT.value in actions:
            previous = private.get("previous_protection_target")
            candidates = [pid for pid in alive if pid not in shunned and pid != previous]
            return AgentDecision(Action.PROTECT.value, {"target": candidates[0]}, "fallback")
        if Action.KILL.value in actions:
            partner = private.get("mafia_private_information", {}).get("partner")
            target = next(pid for pid in others if pid != partner)
            return AgentDecision(Action.KILL.value, {"target": target}, "fallback")
        raise ValueError(f"No required action is available to {self.player_id}")

    async def _gate_target(
        self, decision: AgentDecision, observation: Observation
    ) -> AgentDecision:
        if self.decision_gate is None:
            return decision
        if (
            self.gate_decision_budget is not None
            and self.gate_decisions_used >= self.gate_decision_budget
        ):
            return decision
        target_key = (
            "vote_target"
            if decision.action == Action.SUBMIT_VOTE_DECISION.value
            else "target"
            if decision.action in {
                Action.INVESTIGATE.value,
                Action.PROTECT.value,
                Action.KILL.value,
            }
            else None
        )
        if target_key is None:
            return decision
        options = self._legal_gate_targets(decision.action, observation)
        if not options:
            return decision
        try:
            self.gate_decisions_used += 1
            async with asyncio.timeout(self.gate_timeout_seconds):
                choice, confidence = await self.decision_gate.choose(
                    state={
                        "player_id": self.player_id,
                        "action": decision.action,
                        "public_state": observation.public_state,
                        "your_private_state": observation.private_state,
                        "beliefs": self.state.beliefs,
                    },
                    question_id="target",
                    options=options,
                    instructions="Choose the strongest legal target for this Palermo Nights action.",
                )
        except (ProviderError, TimeoutError):
            return decision
        payload = dict(decision.payload)
        payload[target_key] = choice
        if decision.action == Action.SUBMIT_VOTE_DECISION.value:
            others = [pid for pid in observation.public_state["alive_players"] if pid != self.player_id]
            trusted = payload.get("trusted_player")
            if trusted == choice or trusted not in others:
                trusted = next(pid for pid in reversed(others) if pid != choice)
                payload["trusted_player"] = trusted
            if payload.get("suspect_2") in {choice, trusted}:
                payload["suspect_2"] = next(
                    pid for pid in others if pid not in {choice, trusted}
                )
        confidence_text = "unknown" if confidence is None else f"{confidence:.3f}"
        self.state.strategy = f"typesafe:{decision.action}:{choice}:{confidence_text}"
        return AgentDecision(decision.action, payload, f"{decision.source}+typesafe")

    def _legal_gate_targets(
        self, action: str, observation: Observation
    ) -> list[str]:
        alive = list(observation.public_state["alive_players"])
        shunned = {
            pid
            for pid, data in observation.public_state["players"].items()
            if data["shunned"]
        }
        if action == Action.SUBMIT_VOTE_DECISION.value:
            return [pid for pid in alive if pid != self.player_id]
        if action == Action.KILL.value:
            partner = observation.private_state.get("mafia_private_information", {}).get("partner")
            return [pid for pid in alive if pid not in {self.player_id, partner}]
        if action == Action.PROTECT.value:
            previous = observation.private_state.get("previous_protection_target")
            return [pid for pid in alive if pid not in shunned and pid != previous]
        if action == Action.INVESTIGATE.value:
            return [pid for pid in alive if pid not in shunned]
        return []

    def _parse_decision(
        self, result: dict[str, Any], observation: Observation
    ) -> AgentDecision:
        action = result.get("action")
        if action not in observation.available_actions:
            raise ValueError("Model selected an unavailable action")
        payload = result.get("payload")
        if payload is None:
            payload = {
                key: result.get(key)
                for key in DECISION_FIELDS
            }
        if not isinstance(payload, dict):
            raise ValueError("model_payload_not_object")
        clean_payload = {key: value for key, value in payload.items() if value is not None}
        required = {
            Action.SELECT_STRATEGY.value: ("strategy",),
            Action.ROLE_CLAIM.value: ("claimed_role",),
            Action.SPEAK.value: ("text",),
            Action.ASK.value: ("target", "text"),
            Action.ANSWER.value: ("question_id", "text"),
            Action.SUBMIT_VOTE_DECISION.value: ("vote_target", "trusted_player"),
            Action.INVESTIGATE.value: ("target",),
            Action.PROTECT.value: ("target",),
            Action.KILL.value: ("target",),
        }.get(action, ())
        if any(not clean_payload.get(key) for key in required):
            raise ValueError("model_omitted_required_action_fields")
        return AgentDecision(action, clean_payload)

    def _remember(self, events: list[dict[str, Any]]) -> None:
        for event in events:
            event_id = event.get("event_id")
            if not event_id or event_id in self.state.seen_event_ids:
                continue
            self.state.seen_event_ids.add(event_id)
            importance = 0.9 if event.get("type") in {
                "ROLE_CLAIMED", "VOTE_CAST", "ROLE_REVEALED", "INVESTIGATION_RESULT"
            } else 0.5
            summary = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
            self.state.memory.append(
                AgentMemory(event_id, summary[:500], int(event.get("round", 0)), importance)
            )
        self.state.memory = self.state.memory[-120:]

    def _initialize_beliefs(self, observation: Observation) -> None:
        trust = observation.private_state.get("trust", {})
        for player_id in observation.public_state["alive_players"]:
            if player_id != self.player_id:
                prior = self.state.beliefs.get(player_id, 2 / 6)
                trust_signal = 1 - float(trust.get(player_id, 50)) / 100
                self.state.beliefs[player_id] = round(0.7 * prior + 0.3 * trust_signal, 4)
        for investigation in observation.private_state.get("investigations", []):
            result = investigation.get("result", "")
            self.state.beliefs[investigation["target"]] = (
                1.0 if result in {Role.MAFIA_BOSS.value, Role.MAFIA_DEPUTY.value} else 0.0
            )
        for player_id, role in observation.public_state.get("revealed_roles", {}).items():
            self.state.beliefs[player_id] = (
                1.0 if role in {Role.MAFIA_BOSS.value, Role.MAFIA_DEPUTY.value} else 0.0
            )

    def _apply_agent_state(self, result: dict[str, Any], observation: Observation) -> None:
        updates = result.get("belief_updates", [])
        if isinstance(updates, dict):
            updates = [
                {"player_id": player_id, "mafia_probability": probability}
                for player_id, probability in updates.items()
            ]
        if isinstance(updates, list):
            for update in updates:
                if not isinstance(update, dict):
                    continue
                player_id = update.get("player_id")
                probability = update.get("mafia_probability")
                if player_id in observation.public_state["alive_players"] and player_id != self.player_id:
                    try:
                        self.state.beliefs[player_id] = max(0.0, min(1.0, float(probability)))
                    except (TypeError, ValueError):
                        continue
        summary = result.get("reasoning_summary")
        if isinstance(summary, str) and summary.strip():
            self.state.hypotheses.append(summary.strip()[:500])
            self.state.hypotheses = self.state.hypotheses[-20:]

    def _decision_schema(self, observation: Observation) -> dict[str, Any]:
        actions = observation.available_actions
        alive = observation.public_state["alive_players"]
        others = [pid for pid in alive if pid != self.player_id]
        properties: dict[str, Any] = {
            "action": {"type": "string", "enum": actions},
            "reasoning_summary": {"type": "string", "maxLength": 180},
        }
        required = ["action", "reasoning_summary"]

        def nullable_string(name: str, *, enum: list[str] | None = None) -> None:
            schema: dict[str, Any] = {"type": ["string", "null"]}
            if enum:
                schema["enum"] = [*enum, None]
            properties[name] = schema
            required.append(name)

        if actions == [Action.SELECT_STRATEGY.value]:
            properties["strategy"] = {
                "type": "string",
                "enum": [
                    "ROLE_CLAIM_ATTACK", "CREATE_TWO_SIDES",
                    "FOLLOW_CITIZEN_ERROR_WAVE", "USE_CONTRADICTION",
                ],
            }
            required.append("strategy")
        elif actions == [Action.ROLE_CLAIM.value]:
            properties["claimed_role"] = {
                "type": "string",
                "enum": [role.value for role in Role],
            }
            required.append("claimed_role")
        elif Action.ANSWER.value in actions:
            pending_ids = [
                event["question_id"]
                for event in observation.events
                if event.get("type") == "PLAYER_ASKED"
                and event.get("target") == self.player_id
                and not self._question_answered(observation.events, event["question_id"])
            ]
            properties["question_id"] = {"type": "string", "enum": pending_ids}
            properties["text"] = {"type": "string", "maxLength": 500}
            required.extend(("question_id", "text"))
        elif any(action in actions for action in (Action.SPEAK.value, Action.ASK.value, Action.PASS.value)):
            nullable_string("target", enum=others)
            nullable_string("text")
        elif Action.SUBMIT_VOTE_DECISION.value in actions:
            properties["vote_target"] = {"type": "string", "enum": others}
            properties["trusted_player"] = {"type": "string", "enum": others}
            nullable_string("suspect_2", enum=others)
            required.extend(("vote_target", "trusted_player"))
        elif any(
            action in actions
            for action in (Action.INVESTIGATE.value, Action.PROTECT.value, Action.KILL.value)
        ):
            properties["target"] = {"type": "string", "enum": alive}
            required.append("target")
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": properties,
            "required": required,
        }

    def _system_prompt(self) -> str:
        return (
            "تو یک بازیکن مستقل در بازی استنتاج اجتماعی Palermo Nights هستی. "
            "فقط از state فیلترشده استفاده کن؛ به اطلاعات مخفی سایر بازیکنان دسترسی نداری. "
            "یک action قانونی را انتخاب کن و فقط JSON مطابق schema برگردان. "
            "reasoning_summary باید کوتاه باشد و زنجیره استدلال خصوصی را افشا نکند."
        )

    def _user_prompt(self, observation: Observation) -> str:
        memory = [item.summary for item in self.state.memory[-25:]]
        context = {
            "player_id": self.player_id,
            "public_state": observation.public_state,
            "your_private_state": observation.private_state,
            "legal_actions": observation.available_actions,
            "recent_memory": memory,
            "your_beliefs": self.state.beliefs,
            "instruction": "یک اقدام قانونی و مختصر انتخاب کن. متن‌های گفتگو فارسی باشند.",
        }
        return json.dumps(context, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _safe_failure(exc: Exception) -> str:
        if isinstance(exc, TimeoutError):
            return "decision_timeout"
        if isinstance(exc, ProviderError):
            return f"provider_error:{exc}"
        return f"validation_error:{exc}"

    @staticmethod
    def _question_answered(events: list[dict[str, Any]], question_id: str) -> bool:
        return any(
            event.get("type") == "PLAYER_ANSWERED" and event.get("question_id") == question_id
            for event in events
        )
