"""Regressions from the completed online match of 2026-10-03."""
import json
from copy import deepcopy
from itertools import product

import pytest

from app.ai.agent import AIAgent, AgentDecision
from app.ai.runner import HeadlessGameRunner
from app.ai.service import AIRun, update_run_progress
from app.domain import Phase, PlayerType, Role
from app.engine import GameEngine


class StaticProvider:
    async def generate_json(self, **kwargs):
        self.request = kwargs
        return self.result

    def __init__(self, result):
        self.result = result


def setup_game(role=Role.CITIZEN, phase=Phase.DAY_VOTING):
    engine = GameEngine()
    game = engine.create_game([PlayerType.AI] * 7, seed=42)
    game.phase = phase
    pid = next(pid for pid, p in game.players.items() if p.role == role)
    runner = HeadlessGameRunner(engine, game, {})
    return engine, game, runner, pid


@pytest.mark.anyio
@pytest.mark.parametrize("action", ["SPEAK", "ASK", "ANSWER"])
async def test_missing_dialogue_reference_preserves_text_and_audits_repair(action):
    _, _, runner, pid = setup_game(phase=Phase.DAY_DISCUSSION)
    other = next(p for p in runner.game.players if p != pid)
    text = f"{{{{{other}}}}}، نتیجهٔ شب گذشته را بررسی می‌کنیم."
    provider = StaticProvider({"action": action, "text": text, "target": other if action == "ASK" else None,
                               "referenced_players": []})
    agent = AIAgent(pid, provider, player_names={other: "Marco Conti"})
    decision = await agent.decide(runner.observation(pid, [action]))
    assert decision.source == "model+repaired"
    assert decision.payload["text"] == text.replace(f"{{{{{other}}}}}", "Marco Conti")
    assert decision.corrections == ("dialogue_references_completed",)
    assert agent.last_failure is None


@pytest.mark.anyio
@pytest.mark.parametrize("text,refs", [
    ("{{P99}}", []), ("گفتگو", ["P99"]), ("{{P1}", []),
    ("{{unknown}}", []), ("گفتگو", [{}]), ("گفتگو", "P1"),
])
async def test_reference_repair_does_not_accept_unknown_or_malformed_data(text, refs):
    _, _, runner, pid = setup_game(phase=Phase.DAY_DISCUSSION)
    agent = AIAgent(pid, StaticProvider({"action": "SPEAK", "text": text, "referenced_players": refs}))
    decision = await agent.decide(runner.observation(pid, ["SPEAK"]))
    assert decision.source == "fallback"
    assert agent.last_failure.startswith("validation_error:")


@pytest.mark.anyio
async def test_missing_references_support_single_question_but_not_ambiguous_question():
    _, _, runner, pid = setup_game(phase=Phase.DAY_DISCUSSION)
    a, b = [p for p in runner.game.players if p != pid][:2]
    provider = StaticProvider({"action": "SPEAK", "text": f"{{{{{a}}}}} چرا؟", "referenced_players": []})
    agent = AIAgent(pid, provider)
    obs = runner.observation(pid, ["SPEAK", "ASK", "PASS"])
    decision = await agent.decide(obs)
    assert decision.action == "ASK"
    assert decision.payload["target"] == a
    provider.result["text"] = f"{{{{{a}}}}} و {{{{{b}}}}} چرا؟"
    decision = await agent.decide(obs)
    assert decision.source == "fallback"
    assert agent.last_failure == "validation_error:direct_question_requires_single_target"


@pytest.mark.anyio
async def test_dead_player_can_be_discussed_but_cannot_be_asked():
    _, game, runner, pid = setup_game(phase=Phase.DAY_DISCUSSION)
    dead = next(p for p in game.players if p != pid)
    game.players[dead].alive = False
    provider = StaticProvider({"action": "SPEAK", "text": f"نقش {{{{{dead}}}}} آشکار شده است.", "referenced_players": []})
    agent = AIAgent(pid, provider)
    obs = runner.observation(pid, ["SPEAK", "ASK"])
    decision = await agent.decide(obs)
    assert decision.source == "model+repaired"
    assert dead in provider.request["schema"]["properties"]["referenced_players"]["items"]["enum"]
    assert dead not in provider.request["schema"]["properties"]["target"]["enum"]
    provider.result.update(action="ASK", target=dead)
    assert (await agent.decide(obs)).source == "fallback"


def test_vote_evidence_keeps_public_claims_separate_from_private_data():
    engine, game, runner, pid = setup_game()
    engine._event(game, "PLAYER_SPOKE", {"actor": "P1", "text": "من کارآگاهم."})
    engine._event(game, "INVESTIGATION_RESULT", {"target": "P7", "result": "MAFIA_BOSS"}, "PRIVATE", pid)
    obs = runner.observation(pid)
    agent = AIAgent(pid, StaticProvider({}))
    context = json.loads(agent._user_prompt(obs))
    assert context["public_evidence"][-1]["text"] == "من کارآگاهم."
    assert not any(e["type"] == "INVESTIGATION_RESULT" for e in context["public_evidence"])
    assert not context["timeline"]["can_report_completed_investigation"]
    assert "Do not request" in context["timeline"]["current_guidance"]
    engine._event(game, "NIGHT_RESULT", {"result": "NO_KILL"})
    context = json.loads(agent._user_prompt(runner.observation(pid)))
    assert context["timeline"]["can_report_completed_investigation"]
    assert "unverified claim" in context["timeline"]["current_guidance"]


def test_vote_history_keeps_all_voters_even_after_many_later_statements():
    engine, game, runner, pid = setup_game()
    for voter in ["P3", "P4", "P5"]:
        engine._event(game, "VOTE_CAST", {"actor": voter, "target": "P1"})
    for _ in range(45):
        engine._event(game, "PLAYER_SPOKE", {"actor": "P2", "text": "Only P3 and P4 voted for P1."})
    context = json.loads(AIAgent(pid, StaticProvider({}))._user_prompt(runner.observation(pid)))
    assert [e["actor"] for e in context["vote_history"]] == ["P3", "P4", "P5"]
    assert all(e["target"] == "P1" and e["round"] == 1 for e in context["vote_history"])


@pytest.mark.anyio
async def test_duplicate_vote_preserves_primary_and_is_accepted_by_engine():
    engine, game, runner, pid = setup_game()
    others = [p for p in game.players if p != pid]
    provider = StaticProvider({
        "action": "SUBMIT_VOTE_DECISION", "vote_target": others[0],
        "trusted_player": others[0], "suspect_2": others[0],
    })
    agent = AIAgent(pid, provider)
    decision = await agent.decide(runner.observation(pid))
    assert decision.payload["vote_target"] == others[0]
    assert decision.source == "model+repaired"
    assert decision.corrections == ("trusted_player_reselected", "suspect_2_reselected")
    engine.submit_action(game, pid, decision.action, decision.payload)
    assert game.vote_decisions[pid].vote_target == others[0]


def test_every_vote_combination_can_be_repaired_without_changing_primary():
    engine, game, runner, pid = setup_game()
    agent = AIAgent(pid, StaticProvider({}))
    observation = runner.observation(pid)
    others = [p for p in game.players if p != pid]
    for vote, trust, suspect in product(others, others, [None, *others]):
        decision = agent._validate_targets(AgentDecision("SUBMIT_VOTE_DECISION", {
            "vote_target": vote, "trusted_player": trust, "suspect_2": suspect,
        }), observation)
        trial = deepcopy(game)
        engine.submit_action(trial, pid, decision.action, decision.payload)
        assert trial.vote_decisions[pid].vote_target == vote


@pytest.mark.anyio
async def test_one_remaining_mafia_removes_second_suspect_and_uses_null_schema():
    engine, game, runner, pid = setup_game()
    deputy = next(p for p in game.players.values() if p.role == Role.MAFIA_DEPUTY)
    deputy.alive = False
    engine._event(game, "ROLE_REVEALED", {"player": deputy.player_id, "role": deputy.role.value})
    others = [p.player_id for p in game.players.values() if p.alive and p.player_id != pid]
    provider = StaticProvider({"action": "SUBMIT_VOTE_DECISION", "vote_target": others[0],
                               "trusted_player": others[1], "suspect_2": others[2]})
    agent = AIAgent(pid, provider)
    decision = await agent.decide(runner.observation(pid))
    assert "suspect_2" not in decision.payload
    assert provider.request["schema"]["properties"]["suspect_2"]["type"] == "null"
    engine.submit_action(game, pid, decision.action, decision.payload)


@pytest.mark.parametrize("role,action", [
    (Role.DETECTIVE, "INVESTIGATE"), (Role.DOCTOR, "PROTECT"), (Role.MAFIA_BOSS, "KILL"),
])
def test_night_schema_matches_engine_target_rules(role, action):
    engine, game, runner, pid = setup_game(role, Phase.NIGHT_ACTION)
    others = [p for p in game.players if p != pid]
    game.players[others[0]].shunned = True
    game.players[pid].previous_protection_target = others[1]
    agent = AIAgent(pid, StaticProvider({}))
    observation = runner.observation(pid, [action])
    targets = agent._decision_schema(observation)["properties"]["target"]["enum"]
    for target in targets:
        engine.submit_action(deepcopy(game), pid, action, {"target": target})
    if action in {"INVESTIGATE", "PROTECT"}:
        assert others[0] not in targets
    if action == "PROTECT":
        assert others[1] not in targets
    if action == "KILL":
        assert all(game.players[target].role not in {Role.MAFIA_BOSS, Role.MAFIA_DEPUTY} for target in targets)


@pytest.mark.anyio
async def test_nonconforming_provider_cannot_submit_shunned_investigation():
    engine, game, runner, pid = setup_game(Role.DETECTIVE, Phase.NIGHT_ACTION)
    blocked = next(p for p in game.players if p != pid)
    game.players[blocked].shunned = True
    agent = AIAgent(pid, StaticProvider({"action": "INVESTIGATE", "target": blocked}))
    decision = await agent.decide(runner.observation(pid))
    assert decision.source == "fallback"
    assert agent.last_failure == "validation_error:illegal_night_target"
    assert decision.payload["target"] != blocked
    engine.submit_action(game, pid, decision.action, decision.payload)


@pytest.mark.anyio
async def test_gate_cannot_replace_valid_night_target_with_illegal_one():
    engine, game, runner, pid = setup_game(Role.DETECTIVE, Phase.NIGHT_ACTION)
    blocked, valid = [p for p in game.players if p != pid][:2]
    game.players[blocked].shunned = True

    class BadGate:
        async def choose(self, **kwargs):
            return blocked, 1.0

    agent = AIAgent(pid, StaticProvider({"action": "INVESTIGATE", "target": valid}), decision_gate=BadGate())
    decision = await agent.decide(runner.observation(pid))
    assert decision.payload["target"] == valid
    engine.submit_action(game, pid, decision.action, decision.payload)


def test_timeline_distinguishes_before_and_after_first_ability_night():
    _, game, runner, pid = setup_game(Role.DETECTIVE, Phase.DAY_DISCUSSION)
    agent = AIAgent(pid, StaticProvider({}))
    observation = runner.observation(pid, ["SPEAK"])
    before = json.loads(agent._user_prompt(observation))
    assert before["timeline"]["completed_ability_nights"] == []
    assert before["timeline"]["your_investigations"] == []
    observation.public_state["round"] = 2
    observation.events.append({"type": "NIGHT_RESULT", "round": 1})
    observation.private_state["investigations"] = [{"round": 1, "target": "P7", "result": "CITIZEN"}]
    after = json.loads(agent._user_prompt(observation))
    assert after["timeline"]["completed_ability_nights"] == [1]
    assert after["timeline"]["current_round"] == 2
    assert after["timeline"]["your_investigations"][0]["round"] == 1
    assert "day R+1" in after["timeline"]["investigation_timing"]
    agent._remember([{"text": "x" * 2000, "event_id": "long", "round": 1, "phase": "DAY_DISCUSSION"}])
    assert agent.state.memory[-1].summary.startswith('{"round":1,"phase":"DAY_DISCUSSION"')


@pytest.mark.anyio
async def test_repairs_are_audited_but_not_exposed_publicly(tmp_path, monkeypatch):
    from app.ai import service
    monkeypatch.setattr(service, "AUDIT_DIRECTORY", tmp_path)
    _, game, runner, pid = setup_game()
    run = AIRun(game.game_id, "live")
    runner.on_entry = lambda entry: update_run_progress(run, entry)
    # Use a full model stub run so the runner, audit, and engine all participate.
    class DuplicateVoteAgent(AIAgent):
        async def decide(self, observation):
            self._initialize_beliefs(observation)
            decision = self.fallback_decision(observation)
            if decision.action == "SUBMIT_VOTE_DECISION":
                payload = dict(decision.payload)
                payload["trusted_player"] = payload["vote_target"]
                return self._validate_targets(AgentDecision(decision.action, payload), observation)
            return decision
    runner.agents = {p: DuplicateVoteAgent(p, StaticProvider({})) for p in game.players}
    await runner.run()
    records = [json.loads(line) for line in (tmp_path / f"{game.game_id}.jsonl").read_text().splitlines()]
    assert any(r["corrections"] for r in records)
    assert runner.summary()["recovered_rule_errors"] == 0
    assert runner.summary()["repaired_model_actions"] > 0
    run.summary = runner.summary()
    public = json.dumps(run.public_dict())
    assert "corrections" not in public
    assert "trusted_player_reselected" not in public
