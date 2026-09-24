from __future__ import annotations

import unittest

from app.domain import Action, Faction, Phase, PlayerType, Role, RuleViolation
from app.engine import GameEngine


FIXED_ROLES = [
    Role.MAFIA_BOSS,
    Role.MAFIA_DEPUTY,
    Role.DOCTOR,
    Role.DETECTIVE,
    Role.CITIZEN,
    Role.CITIZEN,
    Role.CITIZEN,
]


class EngineTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = GameEngine()
        self.game = self.engine.create_game(
            [PlayerType.HUMAN, PlayerType.AI, PlayerType.AI, PlayerType.HUMAN,
             PlayerType.AI, PlayerType.AI, PlayerType.HUMAN],
            seed=7,
            fixed_roles=FIXED_ROLES,
        )

    def begin_day_one_voting(self) -> None:
        self.engine.submit_action(
            self.game, "P1", Action.SELECT_STRATEGY, {"strategy": "USE_CONTRADICTION"}
        )
        claims = [
            Role.DETECTIVE,
            Role.CITIZEN,
            Role.DOCTOR,
            Role.DETECTIVE,
            Role.CITIZEN,
            Role.CITIZEN,
            Role.CITIZEN,
        ]
        for index, claim in enumerate(claims, start=1):
            self.engine.submit_action(
                self.game, f"P{index}", Action.ROLE_CLAIM, {"claimed_role": claim.value}
            )
        for player_id in list(self.game.discussion_order):
            self.engine.submit_action(self.game, player_id, Action.PASS, {})
        self.assertEqual(self.game.phase, Phase.DAY_VOTING)

    def vote_for_p6(self) -> None:
        for index in range(1, 8):
            player_id = f"P{index}"
            vote_target = "P6" if player_id != "P6" else "P7"
            excluded = {player_id, vote_target}
            trusted = next(pid for pid in self.game.players if pid not in excluded)
            excluded.add(trusted)
            suspect = next(pid for pid in self.game.players if pid not in excluded)
            self.engine.submit_action(
                self.game,
                player_id,
                Action.SUBMIT_VOTE_DECISION,
                {
                    "vote_target": vote_target,
                    "suspect_2": suspect,
                    "trusted_player": trusted,
                },
            )

    def test_initial_state_is_private_and_roles_are_correct(self) -> None:
        public = self.engine.public_state(self.game)
        self.assertNotIn("actual_roles", public)
        self.assertNotIn("MAFIA_BOSS", str(public))
        self.assertEqual(self.engine.private_state(self.game, "P1")["role"], "MAFIA_BOSS")
        self.assertEqual(
            self.engine.private_state(self.game, "P1")["mafia_private_information"]["partner"],
            "P2",
        )
        self.assertEqual(self.game.players["P4"].trust["P1"], 50)

    def test_player_authentication_is_scoped(self) -> None:
        p1 = self.game.players["P1"]
        self.assertIs(self.engine.authenticate(self.game, "P1", p1.token), p1)
        with self.assertRaisesRegex(RuleViolation, "PLAYER_AUTHENTICATION_FAILED"):
            self.engine.authenticate(self.game, "P2", p1.token)

    def test_day_one_shun_disables_ability_for_one_night(self) -> None:
        self.begin_day_one_voting()
        self.vote_for_p6()
        self.assertEqual(self.game.phase, Phase.NIGHT_ACTION)
        self.assertTrue(self.game.players["P6"].shunned)
        self.assertNotIn(Action.PROTECT.value, self.engine.available_actions(self.game, "P3") if self.game.shunned_player == "P3" else [])

        self.engine.submit_action(self.game, "P4", Action.INVESTIGATE, {"target": "P1"})
        self.engine.submit_action(self.game, "P3", Action.PROTECT, {"target": "P5"})
        self.engine.submit_action(self.game, "P1", Action.KILL, {"target": "P5"})

        self.assertEqual(self.game.last_night_result, {"type": "NO_DEATH"})
        self.assertFalse(self.game.players["P6"].shunned)
        self.assertIsNone(self.game.shunned_player)
        self.assertEqual(self.game.round, 2)
        self.assertEqual(self.game.phase, Phase.DAY_DISCUSSION)

    def test_shunned_role_cannot_act_or_be_investigated(self) -> None:
        self.game.phase = Phase.NIGHT_ACTION
        self.game.players["P4"].shunned = True
        self.game.shunned_player = "P4"
        self.assertNotIn(Action.INVESTIGATE.value, self.engine.available_actions(self.game, "P4"))
        with self.assertRaisesRegex(RuleViolation, "ABILITY_DISABLED_WHILE_SHUNNED"):
            self.engine.submit_action(self.game, "P4", Action.INVESTIGATE, {"target": "P1"})
        with self.assertRaisesRegex(RuleViolation, "SHUNNED_PLAYER_CANNOT_BE_ABILITY_TARGET"):
            self.engine.submit_action(self.game, "P3", Action.PROTECT, {"target": "P4"})

    def test_questions_are_answered_only_after_all_speakers_finish(self) -> None:
        self.engine.submit_action(
            self.game, "P1", Action.SELECT_STRATEGY, {"strategy": "CREATE_TWO_SIDES"}
        )
        for index in range(1, 8):
            self.engine.submit_action(
                self.game,
                f"P{index}",
                Action.ROLE_CLAIM,
                {"claimed_role": Role.CITIZEN.value},
            )
        first = self.game.discussion_order[0]
        target = next(pid for pid in self.game.players if pid != first)
        self.engine.submit_action(
            self.game,
            first,
            Action.ASK,
            {"target": target, "text": "Explain your claim."},
        )
        self.assertNotIn(Action.ANSWER.value, self.engine.available_actions(self.game, target))
        for player_id in self.game.discussion_order[1:]:
            self.engine.submit_action(self.game, player_id, Action.PASS, {})
        self.assertIn(Action.ANSWER.value, self.engine.available_actions(self.game, target))
        question_id = self.game.questions[0].question_id
        self.engine.submit_action(
            self.game,
            target,
            Action.ANSWER,
            {"question_id": question_id, "text": "This is my answer."},
        )
        self.assertEqual(self.game.phase, Phase.DAY_VOTING)

    def test_doctor_cannot_repeat_target_on_consecutive_active_nights(self) -> None:
        self.game.phase = Phase.NIGHT_ACTION
        self.game.players["P3"].previous_protection_target = "P5"
        with self.assertRaisesRegex(
            RuleViolation, "DOCTOR_CANNOT_PROTECT_SAME_TARGET_CONSECUTIVELY"
        ):
            self.engine.submit_action(self.game, "P3", Action.PROTECT, {"target": "P5"})

    def test_investigation_is_visible_only_to_detective(self) -> None:
        self.game.phase = Phase.NIGHT_ACTION
        self.engine.submit_action(self.game, "P4", Action.INVESTIGATE, {"target": "P1"})
        self.engine.submit_action(self.game, "P3", Action.PROTECT, {"target": "P5"})
        self.engine.submit_action(self.game, "P1", Action.KILL, {"target": "P6"})
        detective_events = self.engine.visible_events(self.game, "P4")
        public_events = self.engine.visible_events(self.game)
        self.assertTrue(any(e["type"] == "INVESTIGATION_RESULT" for e in detective_events))
        self.assertFalse(any(e["type"] == "INVESTIGATION_RESULT" for e in public_events))
        self.assertFalse(any(e["type"] == "PLAYER_ELIMINATED" for e in public_events))
        self.assertEqual(sum(e["type"] == "NIGHT_RESULT" for e in public_events), 1)
        self.assertEqual(self.game.players["P4"].investigations[0].result, Role.MAFIA_BOSS)

    def test_tied_vote_updates_trust_but_selects_no_player(self) -> None:
        self.begin_day_one_voting()
        targets = ["P4", "P4", "P4", "P6", "P6", "P7", "P6"]  # 3-3-1
        before = self.game.players["P1"].trust["P4"]
        for index, vote_target in enumerate(targets, start=1):
            player_id = f"P{index}"
            excluded = {player_id, vote_target}
            trusted = next(pid for pid in self.game.players if pid not in excluded)
            excluded.add(trusted)
            suspect = next(pid for pid in self.game.players if pid not in excluded)
            self.engine.submit_action(
                self.game,
                player_id,
                Action.SUBMIT_VOTE_DECISION,
                {
                    "vote_target": vote_target,
                    "suspect_2": suspect,
                    "trusted_player": trusted,
                },
            )
        self.assertIsNone(self.game.shunned_player)
        self.assertEqual(self.game.phase, Phase.NIGHT_ACTION)
        self.assertEqual(self.game.players["P1"].trust["P4"], before - 15)

    def test_deputy_takes_over_kill_when_boss_is_dead(self) -> None:
        self.game.players["P1"].alive = False
        self.game.phase = Phase.NIGHT_ACTION
        self.assertNotIn(Action.KILL.value, self.engine.available_actions(self.game, "P1"))
        self.assertIn(Action.KILL.value, self.engine.available_actions(self.game, "P2"))

    def test_day_two_vote_eliminates_and_reveals_will(self) -> None:
        self.game.phase = Phase.DAY_VOTING
        self.game.round = 2
        self.game.players["P7"].will = "Watch P2 next."
        targets = ["P7", "P7", "P7", "P7", "P7", "P7", "P6"]
        for index, vote_target in enumerate(targets, start=1):
            player_id = f"P{index}"
            excluded = {player_id, vote_target}
            trusted = next(pid for pid in self.game.players if pid not in excluded)
            excluded.add(trusted)
            suspect = next(pid for pid in self.game.players if pid not in excluded)
            self.engine.submit_action(
                self.game,
                player_id,
                Action.SUBMIT_VOTE_DECISION,
                {
                    "vote_target": vote_target,
                    "suspect_2": suspect,
                    "trusted_player": trusted,
                },
            )
        self.assertFalse(self.game.players["P7"].alive)
        public_events = self.engine.visible_events(self.game)
        will = next(event for event in public_events if event["type"] == "WILL_REVEALED")
        self.assertEqual(will["text"], "Watch P2 next.")

    def test_win_conditions_end_game_immediately(self) -> None:
        self.game.players["P1"].alive = False
        self.game.players["P2"].alive = False
        self.assertTrue(self.engine._check_win(self.game))
        self.assertEqual(self.game.winner, Faction.CITIZEN)
        self.assertEqual(self.game.phase, Phase.GAME_OVER)

        game = self.engine.create_game(seed=1, fixed_roles=FIXED_ROLES)
        for pid in ("P5", "P6", "P7"):
            game.players[pid].alive = False
        self.assertTrue(self.engine._check_win(game))
        self.assertEqual(game.winner, Faction.MAFIA)


if __name__ == "__main__":
    unittest.main()
