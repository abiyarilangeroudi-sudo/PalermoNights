"""Optional reference cards. Observations and examples are not reasoning rules."""
from collections import Counter
from ..domain import Phase

VERSION = '2026-10-04.1'
CARDS = [
    {'id': 'votes', 'title': 'Voting coalitions', 'phase': 'DAY',
     'possibilities': ['Shared votes may reflect shared evidence, imitation, coincidence or coordination.', 'Voting against an exposed teammate can also be distancing.'],
     'tradeoff': 'Coalition evidence becomes more informative across independent rounds, but is not proof of role.',
     'counterexample': 'Two citizens can follow the same mistaken accusation.'},
    {'id': 'claims', 'title': 'Claims and timing', 'phase': 'DAY',
     'possibilities': ['A claim can be truthful, mistaken, tactical or a bluff.', 'A reported investigation and an informal suspicion carry different information.'],
     'tradeoff': 'An early claim can gain influence but exposes a valuable role or commits a bluffer to a story.',
     'counterexample': 'Missing a result before the relevant night is not inconsistent with reporting it later.'},
    {'id': 'probability', 'title': 'Uncertainty and base rates', 'phase': 'ANY',
     'possibilities': ['With no distinguishing evidence and m Mafia among n eligible unknown players, the symmetric baseline is m/n.', 'This baseline stops being a personal probability when evidence or selection effects distinguish players.'],
     'tradeoff': 'A numerical estimate depends on assumptions; no tactic has a measured success rate in this library yet.',
     'counterexample': 'The loudest accusation is not an independent observation of the accused role.'},
    {'id': 'distance', 'title': 'Mafia: solidarity or distance', 'phase': 'DAY', 'faction': 'MAFIA',
     'possibilities': ['Defend a teammate.', 'Disagree publicly.', 'Accept losing an exposed teammate.'],
     'tradeoff': 'Solidarity preserves numbers but links identities; distancing can buy credibility but lose voting power.',
     'counterexample': 'Sacrificing a teammate too early may make parity unreachable.'},
    {'id': 'night', 'title': 'Mafia: night target alternatives', 'phase': 'NIGHT', 'faction': 'MAFIA',
     'possibilities': ['Remove an information role.', 'Remove a persuasive organizer.', 'Choose a less protected target.'],
     'tradeoff': 'Role value, social influence, protection and the story the death leaves behind can point to different targets.',
     'counterexample': 'A dangerous-looking target may be protected; a quiet survivor may decide the final vote.'},
    {'id': 'endgame', 'title': 'Mafia: the final votes', 'phase': 'ANY', 'faction': 'MAFIA',
     'possibilities': ['Build on an existing citizen disagreement.', 'Change alliance.', 'Maintain a credible prior position.'],
     'tradeoff': 'Immediate vote arithmetic and long-term credibility need not favor the same choice.',
     'counterexample': 'Winning one vote by revealing coordination can lose the following round.'},
    {'id': 'protection', 'title': 'Night uncertainty', 'phase': 'NIGHT',
     'possibilities': ['Protection can prevent a kill.', 'A blocked attacker can also explain a quiet night.'],
     'tradeoff': 'The public outcome can have multiple private causes.',
     'counterexample': 'No death alone does not identify the protected player or the Mafia.'},
]
_approved = lambda: []


def resources(observation):
    phase = 'NIGHT' if 'NIGHT' in observation.public_state.get('phase', 'DAY_DISCUSSION') else 'DAY'
    faction = observation.private_state.get('faction')
    cards = [c for c in CARDS if c.get('faction', faction) == faction and c['phase'] in {phase, 'ANY'}]
    # Faction-specific examples first; bounded context, freely ignorable.
    cards.sort(key=lambda c: (not bool(c.get('faction')), c['id']))
    return {'version': VERSION, 'optional': True, 'cards': cards[:3],
            'reviewed_lessons': _approved()[:2]}


def analyze_game(game):
    """Postgame evidence, not a claim about hidden thoughts or causal strategy success."""
    public = [e.public_dict() for e in game.events if e.visibility == 'PUBLIC']
    speeches = [e for e in public if e['type'] in {'PLAYER_SPOKE', 'PLAYER_ASKED', 'PLAYER_ANSWERED'}]
    repeated = sum(n - 1 for n in Counter((e.get('actor'), e.get('text', '').strip()) for e in speeches).values() if n > 1)
    votes = [e for e in public if e['type'] == 'VOTE_CAST']
    lessons = []
    if repeated:
        lessons.append({'topic': 'dialogue_repetition', 'observation': f'{repeated} exact repeated statements by the same speakers.',
                        'hypothesis': 'Some turns may add little new information; tactical repetition is also possible.',
                        'evidence': [e['event_id'] for e in speeches], 'counterexample_needed': True})
    if game.phase == Phase.GAME_OVER:
        mistaken = [e for e in votes if game.players[e['actor']].faction == 'CITIZEN' and game.players[e['target']].faction == 'CITIZEN']
        lessons.append({'topic': 'citizen_votes', 'observation': f'{len(mistaken)} citizen votes targeted citizens, as known only after the game.',
                        'hypothesis': 'Review which votes were reasonable with the information available then; a wrong target is not proof of bad reasoning.',
                        'evidence': [e['event_id'] for e in mistaken], 'counterexample_needed': True})
    return {
        'lesson_candidates': lessons,
        'version': VERSION, 'game_id': game.game_id, 'status': 'candidate',
        'complete': game.phase == Phase.GAME_OVER,
        'observed': {'winner': game.winner, 'rounds': game.round, 'votes': len(votes),
                     'dialogue_turns': len(speeches), 'exact_repetitions': repeated},
        'decisions': [{'event_id': e['event_id'], 'round': e['round'], 'actor': e['actor'],
                       'target': e['target'], 'known_before': [x['event_id'] for x in public if x['event_id'] < e['event_id'] and x['type'] in {'ROLE_REVEALED', 'NIGHT_RESULT', 'ROLE_CLAIMED'}]}
                      for e in votes],
        'review_questions': ['Which alternatives were available with the information known at that moment?',
                             'Was a good outcome supported by evidence or compatible with luck?',
                             'What counterexample limits the proposed lesson?'],
        'hypothesis': 'Review the recorded votes and information timing; the outcome alone does not validate a strategy.',
        'limitations': ['No access to private chain of thought.', 'One match does not establish a success probability.',
                       'Candidate lessons are excluded from live reference retrieval until reviewed.'],
    }
