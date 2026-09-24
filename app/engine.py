from __future__ import annotations

import random
import secrets
from collections import Counter
from typing import Any, Iterable

from .domain import (
    Action,
    Event,
    Faction,
    Game,
    Investigation,
    Phase,
    Player,
    PlayerType,
    Question,
    Role,
    RuleViolation,
    VoteDecision,
)


ROLES = [
    Role.MAFIA_BOSS,
    Role.MAFIA_DEPUTY,
    Role.DOCTOR,
    Role.DETECTIVE,
    Role.CITIZEN,
    Role.CITIZEN,
    Role.CITIZEN,
]

STRATEGIES = {
    "ROLE_CLAIM_ATTACK",
    "CREATE_TWO_SIDES",
    "FOLLOW_CITIZEN_ERROR_WAVE",
    "USE_CONTRADICTION",
}


class GameEngine:
    """Pure domain engine. It is the sole writer of authoritative state."""

    def create_game(
        self,
        player_types: Iterable[PlayerType | str] | None = None,
        *,
        seed: int | None = None,
        fixed_roles: Iterable[Role | str] | None = None,
    ) -> Game:
        kinds = list(player_types or [PlayerType.HUMAN] * 7)
        if len(kinds) != 7:
            raise RuleViolation("EXACTLY_SEVEN_PLAYERS_REQUIRED")
        kinds = [PlayerType(kind) for kind in kinds]

        roles = [Role(role) for role in (fixed_roles or ROLES)]
        if Counter(roles) != Counter(ROLES):
            raise RuleViolation("INVALID_ROLE_DISTRIBUTION")
        rng = random.Random(seed)
        if fixed_roles is None:
            rng.shuffle(roles)

        game_id = f"game_{secrets.token_hex(6)}"
        players = {
            f"P{i + 1}": Player(
                player_id=f"P{i + 1}",
                player_type=kinds[i],
                role=roles[i],
                token=secrets.token_urlsafe(24),
            )
            for i in range(7)
        }
        for player in players.values():
            player.trust = {pid: 50 for pid in players if pid != player.player_id}

        game = Game(game_id=game_id, players=players, rng_seed=seed)
        self._event(game, "GAME_CREATED", {"players": list(players)})
        self._event(
            game,
            "ROLES_ASSIGNED",
            {"roles": {pid: player.role.value for pid, player in players.items()}},
            visibility="ENGINE",
        )
        return game

    def authenticate(self, game: Game, player_id: str, token: str | None) -> Player:
        player = game.players.get(player_id)
        if player is None or not token or not secrets.compare_digest(player.token, token):
            raise RuleViolation("PLAYER_AUTHENTICATION_FAILED")
        return player

    def available_actions(self, game: Game, player_id: str) -> list[str]:
        player = self._player(game, player_id)
        if game.phase == Phase.GAME_OVER or not player.alive:
            return []

        actions: list[Action] = [Action.SET_WILL]
        if game.phase == Phase.NIGHT_1_MAFIA:
            if player.role == Role.MAFIA_BOSS and game.mafia_strategy is None:
                actions.append(Action.SELECT_STRATEGY)
        elif game.phase == Phase.ROLE_CLAIM:
            if player.role_claim is None:
                actions.append(Action.ROLE_CLAIM)
        elif game.phase == Phase.DAY_DISCUSSION:
            actions.append(Action.ROLE_CLAIM)
            if self._awaiting_answers(game):
                if any(q.target == player_id and not q.answered for q in game.questions):
                    actions.append(Action.ANSWER)
            elif self._current_speaker(game) == player_id:
                actions.extend((Action.SPEAK, Action.ASK, Action.PASS))
        elif game.phase == Phase.DAY_VOTING:
            if player_id not in game.vote_decisions:
                actions.append(Action.SUBMIT_VOTE_DECISION)
        elif game.phase == Phase.NIGHT_ACTION and not player.shunned:
            required = self._night_actor_action(game, player)
            if required and player_id not in game.night_actions:
                actions.append(required)
        return [action.value for action in actions]

    def submit_action(
        self, game: Game, player_id: str, action: Action | str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        player = self._player(game, player_id)
        if game.phase == Phase.GAME_OVER:
            raise RuleViolation("GAME_ALREADY_OVER")
        if not player.alive:
            raise RuleViolation("DEAD_PLAYER_CANNOT_ACT")
        try:
            action = Action(action)
        except ValueError as exc:
            raise RuleViolation("UNKNOWN_ACTION") from exc

        if action == Action.SET_WILL:
            text = self._text(payload, "text", max_length=1000)
            player.will = text
            self._event(
                game,
                "WILL_UPDATED",
                {"player": player_id, "text": text},
                "PRIVATE",
                player_id,
            )
            return {"success": True}

        if action.value not in self.available_actions(game, player_id):
            if player.shunned and action in (Action.PROTECT, Action.INVESTIGATE, Action.KILL):
                raise RuleViolation("ABILITY_DISABLED_WHILE_SHUNNED")
            raise RuleViolation("ACTION_NOT_AVAILABLE_IN_CURRENT_STATE")

        handlers = {
            Action.SELECT_STRATEGY: self._select_strategy,
            Action.ROLE_CLAIM: self._role_claim,
            Action.SPEAK: self._speak,
            Action.ASK: self._ask,
            Action.ANSWER: self._answer,
            Action.PASS: self._pass,
            Action.SUBMIT_VOTE_DECISION: self._vote,
            Action.INVESTIGATE: self._night_action,
            Action.PROTECT: self._night_action,
            Action.KILL: self._night_action,
        }
        handlers[action](game, player, payload, action)
        return {"success": True, "phase": game.phase.value, "round": game.round}

    def public_state(self, game: Game) -> dict[str, Any]:
        alive = [pid for pid, p in game.players.items() if p.alive]
        return {
            "game_id": game.game_id,
            "phase": game.phase.value,
            "round": game.round,
            "alive_players": alive,
            "players": {
                pid: {
                    "alive": p.alive,
                    "shunned": p.shunned,
                    "player_type": p.player_type.value,
                }
                for pid, p in game.players.items()
            },
            "role_claims": {
                pid: p.role_claim.value
                for pid, p in game.players.items()
                if p.role_claim is not None
            },
            "discussion_order": game.discussion_order if game.phase == Phase.DAY_DISCUSSION else [],
            "shunned_player": game.shunned_player,
            "last_night_result": game.last_night_result,
            "revealed_roles": {
                event.payload["player"]: event.payload["role"]
                for event in game.events
                if event.type == "ROLE_REVEALED"
            },
            "winner": game.winner.value if game.winner else None,
        }

    def private_state(self, game: Game, player_id: str) -> dict[str, Any]:
        player = self._player(game, player_id)
        result: dict[str, Any] = {
            "player_id": player_id,
            "role": player.role.value,
            "faction": player.faction.value,
            "alive": player.alive,
            "shunned": player.shunned,
            "trust": dict(player.trust),
            "investigations": [
                {"round": i.round, "target": i.target, "result": i.result.value}
                for i in player.investigations
            ],
            "previous_protection_target": player.previous_protection_target,
            "will": player.will,
        }
        if player.faction == Faction.MAFIA:
            result["mafia_private_information"] = {
                "partner": next(
                    pid
                    for pid, other in game.players.items()
                    if pid != player_id and other.faction == Faction.MAFIA
                ),
                "strategy": game.mafia_strategy,
            }
        return result

    def visible_events(self, game: Game, player_id: str | None = None) -> list[dict[str, Any]]:
        faction = game.players[player_id].faction if player_id in game.players else None
        visible = []
        for event in game.events:
            if event.visibility == "PUBLIC":
                visible.append(event.public_dict())
            elif event.visibility == "PRIVATE" and event.player_id == player_id:
                visible.append(event.public_dict())
            elif event.visibility == "MAFIA" and faction == Faction.MAFIA:
                visible.append(event.public_dict())
        return visible

    def _select_strategy(self, game: Game, player: Player, payload: dict[str, Any], _: Action) -> None:
        strategy = payload.get("strategy")
        if strategy not in STRATEGIES:
            raise RuleViolation("UNKNOWN_MAFIA_STRATEGY")
        game.mafia_strategy = strategy
        self._event(game, "MAFIA_STRATEGY_SELECTED", {"strategy": strategy}, "MAFIA")
        game.phase = Phase.ROLE_CLAIM

    def _role_claim(self, game: Game, player: Player, payload: dict[str, Any], _: Action) -> None:
        try:
            claimed = Role(payload["claimed_role"])
        except (KeyError, ValueError) as exc:
            raise RuleViolation("INVALID_ROLE_CLAIM") from exc
        player.role_claim = claimed
        self._event(
            game,
            "ROLE_CLAIMED",
            {"actor": player.player_id, "claimed_role": claimed.value},
        )
        if game.phase == Phase.ROLE_CLAIM and all(p.role_claim for p in game.players.values() if p.alive):
            self._start_discussion(game)

    def _speak(self, game: Game, player: Player, payload: dict[str, Any], _: Action) -> None:
        text = self._text(payload, "text")
        self._event(
            game,
            "PLAYER_SPOKE",
            {"actor": player.player_id, "text": text, "discussion_turn": game.discussion_index + 1},
        )
        self._finish_speaking_turn(game)

    def _ask(self, game: Game, player: Player, payload: dict[str, Any], _: Action) -> None:
        target = self._living_target(game, payload.get("target"))
        if target.player_id == player.player_id:
            raise RuleViolation("CANNOT_ASK_SELF")
        text = self._text(payload, "text")
        question = Question(
            question_id=f"q_{game.round}_{len(game.questions) + 1}",
            actor=player.player_id,
            target=target.player_id,
            text=text,
        )
        game.questions.append(question)
        self._event(
            game,
            "PLAYER_ASKED",
            {
                "question_id": question.question_id,
                "actor": player.player_id,
                "target": target.player_id,
                "text": text,
                "discussion_turn": game.discussion_index + 1,
            },
        )
        self._finish_speaking_turn(game)

    def _answer(self, game: Game, player: Player, payload: dict[str, Any], _: Action) -> None:
        pending = [q for q in game.questions if q.target == player.player_id and not q.answered]
        if not pending:
            raise RuleViolation("NO_PENDING_QUESTION")
        question_id = payload.get("question_id")
        question = next((q for q in pending if q.question_id == question_id), None)
        if question is None:
            raise RuleViolation("INVALID_QUESTION_ID")
        text = self._text(payload, "text")
        question.answered = True
        self._event(
            game,
            "PLAYER_ANSWERED",
            {
                "question_id": question.question_id,
                "actor": player.player_id,
                "target": question.actor,
                "text": text,
            },
        )
        if self._awaiting_answers(game) and all(q.answered for q in game.questions):
            game.phase = Phase.DAY_VOTING

    def _pass(self, game: Game, player: Player, payload: dict[str, Any], _: Action) -> None:
        self._event(game, "PLAYER_PASSED", {"actor": player.player_id})
        self._finish_speaking_turn(game)

    def _vote(self, game: Game, player: Player, payload: dict[str, Any], _: Action) -> None:
        vote_target = self._living_target(game, payload.get("vote_target")).player_id
        trusted = self._living_target(game, payload.get("trusted_player")).player_id
        alive_mafia = self._alive_count(game, Faction.MAFIA)
        suspect = payload.get("suspect_2")
        if player.player_id in (vote_target, trusted, suspect):
            raise RuleViolation("VOTE_DECISION_CANNOT_TARGET_SELF")
        if alive_mafia > 1:
            suspect = self._living_target(game, suspect).player_id
            if len({vote_target, trusted, suspect}) != 3:
                raise RuleViolation("VOTE_DECISION_TARGETS_MUST_BE_DISTINCT")
        else:
            if suspect is not None:
                raise RuleViolation("SUSPECT_2_NOT_ALLOWED_WITH_ONE_MAFIA")
            if vote_target == trusted:
                raise RuleViolation("VOTE_AND_TRUST_TARGETS_MUST_DIFFER")
        game.vote_decisions[player.player_id] = VoteDecision(vote_target, trusted, suspect)
        self._event(game, "VOTE_CAST", {"actor": player.player_id, "target": vote_target})
        if len(game.vote_decisions) == len(self._alive_players(game)):
            self._resolve_vote(game)

    def _night_action(self, game: Game, player: Player, payload: dict[str, Any], action: Action) -> None:
        target = self._living_target(game, payload.get("target"))
        if action in (Action.PROTECT, Action.INVESTIGATE) and target.shunned:
            raise RuleViolation("SHUNNED_PLAYER_CANNOT_BE_ABILITY_TARGET")
        if action == Action.PROTECT and player.previous_protection_target == target.player_id:
            raise RuleViolation("DOCTOR_CANNOT_PROTECT_SAME_TARGET_CONSECUTIVELY")
        if action == Action.KILL and target.faction != Faction.CITIZEN:
            raise RuleViolation("MAFIA_CAN_ONLY_TARGET_CITIZENS")
        game.night_actions[player.player_id] = target.player_id
        self._event(
            game,
            "NIGHT_ACTION_SUBMITTED",
            {"actor": player.player_id, "action": action.value, "target": target.player_id},
            "PRIVATE",
            player.player_id,
        )
        if self._all_night_actions_submitted(game):
            self._resolve_night(game)

    def _resolve_vote(self, game: Game) -> None:
        for player_id, decision in game.vote_decisions.items():
            self._change_trust(game, player_id, decision.vote_target, -15, "VOTE_TARGET")
            if decision.suspect_2:
                self._change_trust(game, player_id, decision.suspect_2, -10, "SUSPECT_2")
            self._change_trust(game, player_id, decision.trusted_player, 10, "TRUSTED_PLAYER")

        counts = Counter(decision.vote_target for decision in game.vote_decisions.values())
        top = max(counts.values())
        winners = [pid for pid, count in counts.items() if count == top]
        if len(winners) != 1:
            self._event(game, "VOTE_TIED", {"votes": dict(counts)})
        elif game.round == 1:
            winner = winners[0]
            game.players[winner].shunned = True
            game.shunned_player = winner
            self._event(game, "PLAYER_SHUNNED", {"player": winner})
        else:
            self._eliminate(game, winners[0], "DAY_VOTE")

        game.vote_decisions.clear()
        if self._check_win(game):
            return
        self._start_night(game)

    def _start_night(self, game: Game) -> None:
        game.phase = Phase.NIGHT_ACTION
        game.night_actions.clear()
        self._event(game, "NIGHT_STARTED", {})
        if self._all_night_actions_submitted(game):
            self._resolve_night(game)

    def _resolve_night(self, game: Game) -> None:
        detective = next((p for p in game.players.values() if p.role == Role.DETECTIVE), None)
        doctor = next((p for p in game.players.values() if p.role == Role.DOCTOR), None)
        killer = self._active_killer(game)

        if detective and detective.player_id in game.night_actions:
            target_id = game.night_actions[detective.player_id]
            result = game.players[target_id].role
            detective.investigations.append(Investigation(game.round, target_id, result))
            self._event(
                game,
                "INVESTIGATION_RESULT",
                {"player": detective.player_id, "target": target_id, "result": result.value},
                "PRIVATE",
                detective.player_id,
            )

        protected = None
        if doctor and doctor.player_id in game.night_actions:
            protected = game.night_actions[doctor.player_id]
            doctor.previous_protection_target = protected
            self._event(
                game,
                "PROTECTION_RECORDED",
                {"player": doctor.player_id, "target": protected},
                "PRIVATE",
                doctor.player_id,
            )
        elif doctor:
            # A disabled/dead Doctor did not protect anyone this night, so the
            # consecutive-target restriction resets for the following night.
            doctor.previous_protection_target = None

        killed = None
        mafia_target = game.night_actions.get(killer.player_id) if killer else None
        if mafia_target and mafia_target != protected:
            killed = mafia_target
            # The public learns about a night kill only through NIGHT_RESULT.
            # Internal elimination/reveal events remain available for replay.
            self._eliminate(
                game, killed, "NIGHT_KILL", reveal_will=False, visibility="ENGINE"
            )

        if killed:
            game.last_night_result = {
                "type": "PLAYER_KILLED",
                "player": killed,
                "revealed_role": game.players[killed].role.value,
            }
        else:
            game.last_night_result = {"type": "NO_DEATH"}
        self._event(
            game,
            "NIGHT_RESULT",
            {
                "result": game.last_night_result["type"],
                **{k: v for k, v in game.last_night_result.items() if k != "type"},
            },
        )

        if game.shunned_player:
            game.players[game.shunned_player].shunned = False
            game.shunned_player = None
            self._event(game, "SHUN_CLEARED", {})
        game.night_actions.clear()
        if self._check_win(game):
            return
        game.round += 1
        self._start_discussion(game)

    def _eliminate(
        self,
        game: Game,
        player_id: str,
        reason: str,
        *,
        reveal_will: bool = True,
        visibility: str = "PUBLIC",
    ) -> None:
        player = game.players[player_id]
        player.alive = False
        player.shunned = False
        if game.shunned_player == player_id:
            game.shunned_player = None
        self._event(
            game,
            "PLAYER_ELIMINATED",
            {"player": player_id, "reason": reason},
            visibility,
        )
        self._event(
            game,
            "ROLE_REVEALED",
            {"player": player_id, "role": player.role.value},
            visibility,
        )
        if reveal_will:
            self._event(
                game,
                "WILL_REVEALED",
                {"player": player_id, "text": player.will},
                visibility,
            )

    def _start_discussion(self, game: Game) -> None:
        game.phase = Phase.DAY_DISCUSSION
        game.questions.clear()
        game.discussion_index = 0
        game.discussion_order = [p.player_id for p in self._alive_players(game)]
        random.Random(f"{game.rng_seed}:{game.round}").shuffle(game.discussion_order)
        self._event(game, "DISCUSSION_STARTED", {"order": list(game.discussion_order)})

    def _finish_speaking_turn(self, game: Game) -> None:
        game.discussion_index += 1
        if game.discussion_index >= len(game.discussion_order) and not game.questions:
            game.phase = Phase.DAY_VOTING

    def _awaiting_answers(self, game: Game) -> bool:
        return game.discussion_index >= len(game.discussion_order) and bool(game.questions)

    def _current_speaker(self, game: Game) -> str | None:
        if 0 <= game.discussion_index < len(game.discussion_order):
            return game.discussion_order[game.discussion_index]
        return None

    def _night_actor_action(self, game: Game, player: Player) -> Action | None:
        if player.role == Role.DETECTIVE:
            return Action.INVESTIGATE
        if player.role == Role.DOCTOR:
            return Action.PROTECT
        killer = self._active_killer(game)
        if killer and killer.player_id == player.player_id:
            return Action.KILL
        return None

    def _active_killer(self, game: Game) -> Player | None:
        boss = next((p for p in game.players.values() if p.role == Role.MAFIA_BOSS), None)
        deputy = next((p for p in game.players.values() if p.role == Role.MAFIA_DEPUTY), None)
        if boss and boss.alive:
            return boss
        if deputy and deputy.alive:
            return deputy
        return None

    def _all_night_actions_submitted(self, game: Game) -> bool:
        required = {
            p.player_id
            for p in self._alive_players(game)
            if not p.shunned and self._night_actor_action(game, p) is not None
        }
        return required <= set(game.night_actions)

    def _check_win(self, game: Game) -> bool:
        mafia = self._alive_count(game, Faction.MAFIA)
        citizens = self._alive_count(game, Faction.CITIZEN)
        winner = Faction.CITIZEN if mafia == 0 else Faction.MAFIA if mafia == citizens else None
        if winner is None:
            return False
        game.winner = winner
        game.phase = Phase.GAME_OVER
        self._event(
            game,
            "GAME_OVER",
            {"winner": winner.value, "alive_mafia": mafia, "alive_citizens": citizens},
        )
        return True

    def _change_trust(
        self, game: Game, player_id: str, target: str, delta: int, reason: str
    ) -> None:
        player = game.players[player_id]
        old = player.trust[target]
        player.trust[target] = max(1, min(100, old + delta))
        self._event(
            game,
            "TRUST_UPDATED",
            {
                "player": player_id,
                "target": target,
                "delta": delta,
                "value": player.trust[target],
                "reason": reason,
            },
            "PRIVATE",
            player_id,
        )

    def _event(
        self,
        game: Game,
        event_type: str,
        payload: dict[str, Any],
        visibility: str = "PUBLIC",
        player_id: str | None = None,
    ) -> None:
        game.events.append(
            Event(
                event_id=f"evt_{len(game.events) + 1:06d}",
                type=event_type,
                round=game.round,
                phase=game.phase.value,
                payload=payload,
                visibility=visibility,
                player_id=player_id,
            )
        )

    @staticmethod
    def _text(payload: dict[str, Any], key: str, max_length: int = 2000) -> str:
        text = payload.get(key)
        if not isinstance(text, str) or not text.strip() or len(text) > max_length:
            raise RuleViolation("INVALID_TEXT")
        return text.strip()

    @staticmethod
    def _player(game: Game, player_id: str) -> Player:
        try:
            return game.players[player_id]
        except KeyError as exc:
            raise RuleViolation("PLAYER_NOT_FOUND") from exc

    def _living_target(self, game: Game, player_id: Any) -> Player:
        if not isinstance(player_id, str) or player_id not in game.players:
            raise RuleViolation("INVALID_TARGET")
        target = game.players[player_id]
        if not target.alive:
            raise RuleViolation("TARGET_NOT_ALIVE")
        return target

    @staticmethod
    def _alive_players(game: Game) -> list[Player]:
        return [player for player in game.players.values() if player.alive]

    @staticmethod
    def _alive_count(game: Game, faction: Faction) -> int:
        return sum(p.alive and p.faction == faction for p in game.players.values())
