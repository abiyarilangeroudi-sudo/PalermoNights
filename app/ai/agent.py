from __future__ import annotations

import asyncio
import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any

from ..domain import Action, CLAIMABLE_ROLES, Role
from .evidence import dossier, assessment_schema, public_events
from .library import resources
from .reasoning import checked_decision, clean_text
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
    belief_epoch: str | None = None
    assessments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AgentDecision:
    action: str
    payload: dict[str, Any]
    source: str = "model"
    corrections: tuple[str, ...] = ()


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
        language: str = "fa",
        player_names: dict[str, str] | None = None,
        require_assessment: bool = False,
    ) -> None:
        self.require_assessment = require_assessment
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
        self.language = language if language in {"fa", "en", "de"} else "fa"
        self.player_names = dict(player_names or {})
        self.last_failure: str | None = None
        self.state = AgentState()
        self.checkpoint = None

    async def decide(self, observation: Observation) -> AgentDecision:
        self._remember(observation.events)
        self._initialize_beliefs(observation)
        if (
            self.remote_decision_budget is not None
            and self.remote_decisions_used >= self.remote_decision_budget
        ):
            fallback = self.fallback_decision(observation)
            return checked_decision(self, await self._gate_target(fallback, observation), {}, observation)
        max_tokens = (
            self.speak_max_output_tokens
            if any(action in observation.available_actions for action in ("SPEAK", "ASK", "ANSWER"))
            else self.max_output_tokens
        )
        try:
            self.remote_decisions_used += 1
            if self.checkpoint:
                self.checkpoint()
            schema = self._decision_schema(observation)
            async with asyncio.timeout(self.decision_timeout_seconds):
                result = await self.provider.generate_json(
                    system_prompt=self._system_prompt(),
                    user_prompt=self._user_prompt(observation),
                    schema=schema,
                    max_output_tokens=max_tokens,
                )
            if self.require_assessment and result.get("action") in {"SPEAK", "ASK", "ANSWER", "SUBMIT_VOTE_DECISION"} and "assessment" not in result:
                raise ValueError("model_omitted_assessment")
            decision = self._parse_decision(result, observation)
            decision = await self._gate_target(decision, observation)
            decision = self._validate_targets(decision, observation)
            decision = checked_decision(self, decision, result, observation)
            self._apply_agent_state(result, observation)
            self.last_failure = None
            return decision
        except (ProviderError, TimeoutError, ValueError, KeyError, TypeError) as exc:
            self.last_failure = self._safe_failure(exc)
            fallback = self.fallback_decision(observation)
            return checked_decision(self, await self._gate_target(fallback, observation), {}, observation)

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
            return AgentDecision(
                Action.ANSWER.value,
                {"text": self._fallback_text("answer")},
                "fallback",
            )
        if Action.SPEAK.value in actions:
            return AgentDecision(
                Action.SPEAK.value,
                {"text": self._fallback_text("speak")},
                "fallback",
            )
        if Action.PASS.value in actions:
            return AgentDecision(Action.PASS.value, {}, "fallback")
        if Action.SUBMIT_VOTE_DECISION.value in actions:
            ranked = sorted(
                others,
                key=lambda pid: self._fallback_suspicion(pid, observation),
                reverse=True,
            )
            partner = private.get("mafia_private_information", {}).get("partner")
            legal_suspects = [pid for pid in ranked if pid != partner] or ranked
            vote_target = legal_suspects[0]
            payload: dict[str, Any] = {"vote_target": vote_target}
            return AgentDecision(Action.SUBMIT_VOTE_DECISION.value, payload, "fallback")
        if Action.INVESTIGATE.value in actions:
            known = {item["target"] for item in private.get("investigations", [])}
            known.update(public.get("revealed_roles", {}))
            candidates = [pid for pid in others if pid not in shunned]
            unknown = [pid for pid in candidates if pid not in known]
            # Prefer maximum uncertainty (and thus information gain). If every
            # legal target is known, an investigation is still required.
            target = min(
                unknown or candidates,
                key=lambda pid: (abs(self.state.beliefs.get(pid, 0.5) - 0.5), pid),
            )
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

    def _fallback_suspicion(self, player_id: str, observation: Observation) -> float:
        """Evidence-based deterministic fallback; never depends on player order."""
        public = observation.public_state
        private = observation.private_state
        score = 100 * float(self.state.beliefs.get(player_id, 2 / 6))
        score += 0.7 * (50 - float(private.get("trust", {}).get(player_id, 50)))
        claim = public.get("role_claims", {}).get(player_id)
        if claim in {Role.DOCTOR.value, Role.DETECTIVE.value}:
            confirmed_elsewhere = any(
                other_id != player_id and role == claim
                for other_id, role in public.get("revealed_roles", {}).items()
            )
            if confirmed_elsewhere:
                score += 120
        material = (
            f"{public.get('game_id')}:{public.get('round')}:{self.player_id}:{player_id}"
        ).encode()
        score += int.from_bytes(hashlib.sha256(material).digest()[:2], "big") / 65535
        return score

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
        if not options or decision.payload.get(target_key) in options:
            return decision
        try:
            self.gate_decisions_used += 1
            if self.checkpoint:
                self.checkpoint()
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
                    instructions="Return a legal target for an otherwise invalid action.",
                )
        except (ProviderError, TimeoutError):
            return decision
        payload = dict(decision.payload)
        payload[target_key] = choice
        if choice not in options:
            return decision
        confidence_text = "unknown" if confidence is None else f"{confidence:.3f}"
        self.state.strategy = f"typesafe:{decision.action}:{choice}:{confidence_text}"
        return self._validate_targets(
            AgentDecision(decision.action, payload, f"{decision.source}+typesafe", decision.corrections),
            observation,
        )

    @staticmethod
    def _needs_second_suspect(observation: Observation) -> bool:
        # Eliminated roles are public. Never inspect another player's private role.
        return not any(
            role in {Role.MAFIA_BOSS.value, Role.MAFIA_DEPUTY.value}
            for role in observation.public_state.get("revealed_roles", {}).values()
        )

    def _validate_targets(self, decision: AgentDecision, observation: Observation) -> AgentDecision:
        action = decision.action
        if action in {Action.INVESTIGATE.value, Action.PROTECT.value, Action.KILL.value}:
            if decision.payload.get("target") not in self._legal_gate_targets(action, observation):
                raise ValueError("illegal_night_target")
        if action != Action.SUBMIT_VOTE_DECISION.value:
            return decision
        others = self._legal_gate_targets(action, observation)
        payload = dict(decision.payload)
        vote = payload.get("vote_target")
        if vote not in others:
            raise ValueError("illegal_vote_target")
        corrections = list(decision.corrections)
        used = {vote}
        for key in ("suspect_2", "trusted_player"):
            value = payload.get(key)
            if observation.private_state.get("faction") == "MAFIA" or value not in others or value in used:
                if value is not None:
                    corrections.append(key + "_removed")
                payload.pop(key, None)
            elif value is not None:
                used.add(value)

        return AgentDecision(action, payload, "model+repaired" if corrections and decision.source == "model" else decision.source, tuple(corrections))

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
            Action.ANSWER.value: ("text",),
            Action.SUBMIT_VOTE_DECISION.value: ("vote_target",),
            Action.INVESTIGATE.value: ("target",),
            Action.PROTECT.value: ("target",),
            Action.KILL.value: ("target",),
        }.get(action, ())
        if any(not clean_payload.get(key) for key in required):
            raise ValueError("model_omitted_required_action_fields")
        corrections: tuple[str, ...] = ()
        if action in {Action.SPEAK.value, Action.ASK.value, Action.ANSWER.value}:
            supplied = result.get("referenced_players", [])
            references = self._dialogue_references(str(clean_payload["text"]), supplied, observation)
            if set(references) != set(supplied):
                corrections = ("dialogue_references_completed",)
            clean_payload["text"] = self._validated_dialogue(
                str(clean_payload["text"]),
                references,
                observation,
            )
            references = [
                player_id
                for player_id in references
                if player_id != self.player_id
            ]
            if action == Action.SPEAK.value and (
                clean_payload.get("target") or re.search(r"[?؟]", clean_payload["text"])
            ):
                target = clean_payload.get("target")
                if target not in references:
                    target = references[0] if len(references) == 1 else None
                if target is None:
                    raise ValueError("direct_question_requires_single_target")
                action = Action.ASK.value
                clean_payload["target"] = target
            if action == Action.ASK.value:
                target = clean_payload.get("target")
                if target not in references or target not in observation.public_state["alive_players"]:
                    raise ValueError("ask_target_must_be_referenced")
        return AgentDecision(action, clean_payload, "model+repaired" if corrections else "model", corrections)

    def _dialogue_references(
        self, value: str, supplied: Any, observation: Observation
    ) -> list[str]:
        if not isinstance(supplied, list) or not all(isinstance(pid, str) for pid in supplied):
            raise ValueError("dialogue_references_not_array_of_strings")
        known = set(observation.public_state["players"])
        placeholders = set(re.findall(r"\{\{(P\d+)\}\}", value))
        if not (set(supplied) | placeholders) <= known:
            raise ValueError("dialogue_referenced_unknown_player")
        # Only restore unambiguous, existing IDs; never guess a character name.
        return list(dict.fromkeys([*supplied, *sorted(placeholders)]))

    def _validated_dialogue(
        self,
        value: str,
        referenced_players: Any,
        observation: Observation,
    ) -> str:
        if not isinstance(referenced_players, list):
            raise ValueError("dialogue_references_not_array")
        known = set(observation.public_state["players"])
        references = set(referenced_players)
        if not references <= known:
            raise ValueError("dialogue_referenced_unknown_player")
        raw_names = [name for name in self.player_names.values() if name and name in value]
        if raw_names:
            raise ValueError("dialogue_must_use_player_placeholders")
        placeholders = set(re.findall(r"\{\{(P\d+)\}\}", value))
        if not placeholders <= references:
            raise ValueError("dialogue_reference_mismatch")
        rendered = value
        for player_id in placeholders:
            rendered = rendered.replace(
                f"{{{{{player_id}}}}}", self.player_names.get(player_id, player_id)
            )
        if "{{" in rendered or "}}" in rendered:
            raise ValueError("dialogue_contains_unknown_placeholder")
        return clean_text(rendered, self.language)

    def _remember(self, events: list[dict[str, Any]]) -> None:
        for event in events:
            event_id = event.get("event_id")
            if not event_id or event_id in self.state.seen_event_ids:
                continue
            self.state.seen_event_ids.add(event_id)
            importance = 0.9 if event.get("type") in {
                "ROLE_CLAIMED", "VOTE_CAST", "ROLE_REVEALED", "INVESTIGATION_RESULT"
            } else 0.5
            # Put chronology before dialogue so truncation cannot erase its date.
            summary = json.dumps(
                {"round": event.get("round"), "phase": event.get("phase"), **event},
                ensure_ascii=False, separators=(",", ":"),
            )
            self.state.memory.append(
                AgentMemory(event_id, summary[:500], int(event.get("round", 0)), importance)
            )
        self.state.memory = self.state.memory[-120:]

    def _initialize_beliefs(self, observation: Observation) -> None:
        trust = observation.private_state.get("trust", {})
        epoch = json.dumps(trust, sort_keys=True)
        for player_id in observation.public_state["alive_players"]:
            if player_id != self.player_id and (epoch != self.state.belief_epoch or player_id not in self.state.beliefs):
                prior = self.state.beliefs.get(player_id, 2 / 6)
                trust_signal = 1 - float(trust.get(player_id, 50)) / 100
                self.state.beliefs[player_id] = round(0.7 * prior + 0.3 * trust_signal, 4)
        self.state.belief_epoch = epoch
        self._pin_known_roles(observation)

    def _pin_known_roles(self, observation: Observation) -> None:
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
        self._pin_known_roles(observation)
        summary = result.get("reasoning_summary")
        if isinstance(summary, str) and summary.strip():
            self.state.hypotheses.append(summary.strip()[:500])
            self.state.hypotheses = self.state.hypotheses[-20:]

    def _decision_schema(self, observation: Observation) -> dict[str, Any]:
        actions = observation.available_actions
        alive = observation.public_state["alive_players"]
        others = [pid for pid in alive if pid != self.player_id]
        known = list(observation.public_state["players"]) or alive
        properties: dict[str, Any] = {
            "action": {"type": "string", "enum": actions},
            "reasoning_summary": {
                "type": "string", "maxLength": 180,
                "description": "Brief decision justification, not private reasoning. For votes mention a relevant evidence event ID if available, otherwise acknowledge weak evidence. Never invent evidence.",
            },
        }
        required = ["action", "reasoning_summary"]

        def nullable_string(
            name: str,
            *,
            enum: list[str] | None = None,
            max_length: int | None = None,
        ) -> None:
            schema: dict[str, Any] = {"type": ["string", "null"]}
            if enum:
                schema["enum"] = [*enum, None]
            if max_length is not None:
                schema["maxLength"] = max_length
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
                "enum": [role.value for role in CLAIMABLE_ROLES],
            }
            required.append("claimed_role")
        elif Action.ANSWER.value in actions:
            properties["text"] = {"type": "string", "maxLength": 1200}
            properties["referenced_players"] = {
                "type": "array", "items": {"type": "string", "enum": known},
            }
            required.extend(("text", "referenced_players"))
        elif any(action in actions for action in (Action.SPEAK.value, Action.ASK.value, Action.PASS.value)):
            nullable_string("target", enum=others)
            nullable_string("text", max_length=500)
            properties["referenced_players"] = {
                "type": "array", "items": {"type": "string", "enum": known},
            }
            required.append("referenced_players")
        elif Action.SUBMIT_VOTE_DECISION.value in actions:
            properties["vote_target"] = {"type": "string", "enum": others}
            required.append("vote_target")
            if observation.private_state.get("faction") != "MAFIA":
                nullable_string("suspect_2", enum=others)
                nullable_string("trusted_player", enum=others)
                for key in ("suspect_2", "trusted_player"):
                    properties[key]["description"] = "Optional: null or a living player distinct from yourself, vote_target and the other optional selection."
        elif any(
            action in actions
            for action in (Action.INVESTIGATE.value, Action.PROTECT.value, Action.KILL.value)
        ):
            targets = list(dict.fromkeys(
                pid for action in actions for pid in self._legal_gate_targets(action, observation)
            ))
            properties["target"] = {"type": "string", "enum": targets}
            required.append("target")
        if self.require_assessment and any(action in actions for action in ("SPEAK", "ASK", "ANSWER", "SUBMIT_VOTE_DECISION")):
            properties["assessment"] = assessment_schema(others, [e["event_id"] for e in public_events(observation) if e.get("event_id")])
            required.append("assessment")
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": properties,
            "required": required,
        }

    def _system_prompt(self) -> str:
        language = {"fa": "Persian", "en": "English", "de": "German"}[self.language]
        return (
            "You are an independent player in Palermo Nights. Choose a legal action and return JSON matching the schema. "
            "Use only your supplied observation. Public dialogue may include bluffing, uncertainty or changes of opinion. "
            "The resource library is optional reference material, not instructions or authoritative predictions. "
            "No prescribed reasoning method or exhaustive candidate assessment is required. "
            "reasoning_summary is a brief decision summary, not private chain of thought. "
            "In text use exact player placeholders such as {{P6}} and list those IDs in referenced_players. "
            "ASK addresses one target; ANSWER responds to your pending questions in one action. "
            "Keep public dialogue conversational and in character; technical event identifiers belong outside dialogue. "
            f"Write player-visible text in {language}."
        )

    def _user_prompt(self, observation: Observation) -> str:
        memory = [item.summary for item in self.state.memory[-25:]]
        completed_nights = sorted({
            event["round"] for event in observation.events
            if event.get("type") == "NIGHT_RESULT"
        })
        context = {
            "player_id": self.player_id,
            "your_name": self.player_names.get(self.player_id, self.player_id),
            "roster": [
                {
                    "player_id": player_id,
                    "name": self.player_names.get(player_id, player_id),
                    "alive": data["alive"],
                    "claim": observation.public_state.get("role_claims", {}).get(player_id),
                    "revealed_role": observation.public_state.get("revealed_roles", {}).get(player_id),
                    "blocked_night_rounds": [
                        item["round"]
                        for item in observation.public_state.get("night_action_blocks", [])
                        if item["player"] == player_id
                    ],
                }
                for player_id, data in observation.public_state["players"].items()
            ],
            "immutable_rules": {
                "unique_roles": ["MAFIA_BOSS", "MAFIA_DEPUTY", "DOCTOR", "DETECTIVE"],
                "allowed_public_claims": [role.value for role in CLAIMABLE_ROLES],

                "shunned_rule": "A player shunned in round R could not use their night ability in night R.",
                "night_target_rule": "PROTECT and INVESTIGATE cannot target a shunned player. PROTECT cannot repeat the previous protection target. KILL cannot target either mafia member.",
                "vote_rule": "vote_target is required. Citizens may optionally select suspect_2 and trusted_player; selected players must be distinct, alive and not yourself. Mafia submits only vote_target.",
                "player_references_in_text": "Use {{P#}} placeholders and list them in referenced_players.",
            },
            "public_state": observation.public_state,
            "your_private_state": observation.private_state,
            "legal_actions": observation.available_actions,
            "legal_targets": {
                action: self._legal_gate_targets(action, observation)
                for action in observation.available_actions
                if action in {Action.SUBMIT_VOTE_DECISION.value, Action.INVESTIGATE.value, Action.PROTECT.value, Action.KILL.value}
            },
            "second_suspect_required": False,
            "vote_history": [
                {key: event[key] for key in ("round", "actor", "target")}
                for event in observation.events if event.get("type") == "VOTE_CAST"
                and event.get("visibility") == "PUBLIC"
            ],
            "public_evidence": [
                {key: event[key] for key in (
                    "event_id", "type", "round", "phase", "actor", "target", "targets",
                    "player", "role", "claimed_role", "text", "result", "revealed_role",
                ) if key in event}
                for event in observation.events
                if event.get("visibility") == "PUBLIC" and event.get("type") in {
                    "ROLE_CLAIMED", "ROLE_REVEALED", "NIGHT_RESULT", "PLAYER_SPOKE",
                    "PLAYER_ASKED", "PLAYER_ANSWERED", "VOTE_CAST",
                }
            ][-24:],
            "timeline": {
                "current_round": observation.public_state.get("round"),
                "current_phase": observation.public_state.get("phase"),
                "completed_ability_nights": completed_nights,
                "can_report_completed_investigation": bool(completed_nights),
                "investigation_timing": "Introduction night has no investigation. Day 1 precedes ability night 1. An investigation from night R can be reported on day R+1; this is new evidence, not a contradiction with having no result on day R.",
                "your_investigations": observation.private_state.get("investigations", []),
            },
            "pending_questions_for_you": [
                event
                for event in observation.events
                if event.get("type") == "PLAYER_ASKED"
                and event.get("target") == self.player_id
                and not self._question_answered(observation.events, event["question_id"])
            ],
            "casebook": dossier(observation),
            "optional_library": resources(observation),
            "recent_hypotheses": self.state.hypotheses[-5:],
            "recent_memory": memory,
            "your_beliefs": self.state.beliefs,
            "instruction": {
                "fa": "یک اقدام قانونی و مختصر انتخاب کن. متن گفتگو حداکثر سه جملهٔ کوتاه فارسی باشد. برای نام بازیکنان فقط placeholder مانند {{P2}} بنویس؛ نام نمایشی را سرور جایگزین می‌کند.",
                "en": "Choose one concise legal action. Use at most three short English sentences. Refer to players using placeholders such as {{P2}}; the server inserts character names.",
                "de": "Wähle eine kurze legale Aktion in höchstens drei kurzen deutschen Sätzen. Verwende Spielerplatzhalter wie {{P2}}; der Server setzt Figurennamen ein.",
            }[self.language],
        }
        return json.dumps(context, ensure_ascii=False, separators=(",", ":"))

    def _fallback_text(self, kind: str) -> str:
        texts = {
            "fa": {
                "speak": "فعلاً به تناقض ادعاها و الگوی رأی‌ها توجه می‌کنم.",
                "answer": "رأی و ادعایم را بر اساس شواهد عمومی توضیح می‌دهم.",
            },
            "en": {
                "speak": "For now, I am watching contradictions and voting patterns.",
                "answer": "I will explain my claim and vote using the public evidence.",
            },
            "de": {
                "speak": "Vorerst achte ich auf Widersprüche und Abstimmungsmuster.",
                "answer": "Ich begründe meine Behauptung und Stimme mit öffentlichen Hinweisen.",
            },
        }
        return texts[self.language][kind]

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
            event.get("type") == "PLAYER_ANSWERED"
            and (
                event.get("question_id") == question_id
                or question_id in event.get("question_ids", [])
            )
            for event in events
        )
