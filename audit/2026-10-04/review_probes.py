"""Offline review probes. No network/model calls; does not modify running games."""
import asyncio
import json
import sys
from collections import Counter
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.ai.service import AIRun, build_runner, execute_run, update_run_progress
from app.domain import PlayerType, Role
from app.engine import GameEngine


async def main():
    result = {}
    wins, failures, kills = Counter(), [], Counter()
    rounds = []
    for seed in range(200):
        engine = GameEngine()
        game = engine.create_game([PlayerType.AI] * 7, seed=seed)
        game.game_id = f"review_{seed}"
        runner = build_runner(engine, game, mode="offline", settings=None, live_action_budget=None)
        try:
            await runner.run()
            wins[game.winner.value] += 1
            rounds.append(game.round)
            first = next((e for e in game.events if e.type == "NIGHT_ACTION_SUBMITTED" and e.payload['action'] == 'KILL'), None)
            if first:
                kills[first.payload['target']] += 1
        except Exception as exc:
            failures.append({"seed": seed, "error": type(exc).__name__, "phase": game.phase.value})
    result['offline_200'] = {"wins": dict(wins), "failures": failures, "rounds_min_max": [min(rounds),max(rounds)], "first_attack_targets": dict(kills)}

    engine = GameEngine()
    roles = [Role.MAFIA_BOSS, Role.MAFIA_DEPUTY, Role.DOCTOR, Role.DETECTIVE, Role.CITIZEN, Role.CITIZEN, Role.CITIZEN]
    game = engine.create_game([PlayerType.HUMAN, *([PlayerType.AI]*6)], fixed_roles=roles)
    run = AIRun(game_id=game.game_id, mode='offline', human_player_id='P1')
    runner = build_runner(engine, game, mode='offline', settings=None, live_action_budget=None, on_entry=lambda entry: update_run_progress(run, entry))
    await execute_run(run, runner)
    with patch('app.ai.service._write_audit_record', side_effect=OSError('simulated disk failure')):
        try:
            runner.submit_participant_decision('P1', 'SELECT_STRATEGY', {'strategy':'USE_CONTRADICTION'}, source='human', required_actions=run.awaiting_actions)
        except OSError:
            result['audit_write_failure'] = {"phase_after_error":game.phase.value,"run_status":run.status,"stale_awaiting":run.awaiting_actions,"actual_required":runner.required_actions('P1')}

    agent = runner.agents['P3']
    observation = runner.observation('P3')
    values = []
    for _ in range(8):
        agent._initialize_beliefs(observation)
        values.append(agent.state.beliefs['P5'])
    result['unchanged_evidence_belief_drift'] = values
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    asyncio.run(main())
