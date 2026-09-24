from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class Role(StrEnum):
    MAFIA_BOSS = "MAFIA_BOSS"
    MAFIA_DEPUTY = "MAFIA_DEPUTY"
    DOCTOR = "DOCTOR"
    DETECTIVE = "DETECTIVE"
    CITIZEN = "CITIZEN"


class Faction(StrEnum):
    MAFIA = "MAFIA"
    CITIZEN = "CITIZEN"


class PlayerType(StrEnum):
    HUMAN = "HUMAN"
    AI = "AI"


class Phase(StrEnum):
    NIGHT_1_MAFIA = "NIGHT_1_MAFIA"
    ROLE_CLAIM = "ROLE_CLAIM"
    DAY_DISCUSSION = "DAY_DISCUSSION"
    DAY_VOTING = "DAY_VOTING"
    NIGHT_ACTION = "NIGHT_ACTION"
    GAME_OVER = "GAME_OVER"


class Action(StrEnum):
    SELECT_STRATEGY = "SELECT_STRATEGY"
    ROLE_CLAIM = "ROLE_CLAIM"
    SPEAK = "SPEAK"
    ASK = "ASK"
    ANSWER = "ANSWER"
    PASS = "PASS"
    SUBMIT_VOTE_DECISION = "SUBMIT_VOTE_DECISION"
    INVESTIGATE = "INVESTIGATE"
    PROTECT = "PROTECT"
    KILL = "KILL"
    SET_WILL = "SET_WILL"


def faction_for(role: Role) -> Faction:
    if role in (Role.MAFIA_BOSS, Role.MAFIA_DEPUTY):
        return Faction.MAFIA
    return Faction.CITIZEN


@dataclass(slots=True)
class Investigation:
    round: int
    target: str
    result: Role


@dataclass(slots=True)
class Player:
    player_id: str
    player_type: PlayerType
    role: Role
    token: str
    alive: bool = True
    shunned: bool = False
    role_claim: Role | None = None
    trust: dict[str, int] = field(default_factory=dict)
    investigations: list[Investigation] = field(default_factory=list)
    previous_protection_target: str | None = None
    will: str = ""

    @property
    def faction(self) -> Faction:
        return faction_for(self.role)


@dataclass(slots=True)
class Event:
    event_id: str
    type: str
    round: int
    phase: str
    payload: dict[str, Any]
    visibility: str = "PUBLIC"
    player_id: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def public_dict(self) -> dict[str, Any]:
        return {
            **self.payload,
            "event_id": self.event_id,
            "type": self.type,
            "round": self.round,
            "phase": self.phase,
            "visibility": self.visibility,
            "created_at": self.created_at,
        }


@dataclass(slots=True)
class Question:
    question_id: str
    actor: str
    target: str
    text: str
    answered: bool = False


@dataclass(slots=True)
class VoteDecision:
    vote_target: str
    trusted_player: str
    suspect_2: str | None = None


@dataclass(slots=True)
class Game:
    game_id: str
    players: dict[str, Player]
    phase: Phase = Phase.NIGHT_1_MAFIA
    round: int = 1
    winner: Faction | None = None
    mafia_strategy: str | None = None
    events: list[Event] = field(default_factory=list)
    questions: list[Question] = field(default_factory=list)
    discussion_order: list[str] = field(default_factory=list)
    discussion_index: int = 0
    vote_decisions: dict[str, VoteDecision] = field(default_factory=dict)
    night_actions: dict[str, str] = field(default_factory=dict)
    shunned_player: str | None = None
    last_night_result: dict[str, Any] | None = None
    rng_seed: int | None = None


class RuleViolation(Exception):
    def __init__(self, code: str, message: str | None = None):
        self.code = code
        self.message = message or code
        super().__init__(self.message)
