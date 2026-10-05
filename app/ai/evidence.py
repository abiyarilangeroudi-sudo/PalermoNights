"""Evidence dossiers derived solely from the participant's filtered observation.

Role revelations reclassify old claims, never retroactively change what a voter
knew. Associations are comparisons, not automatic guilt/innocence scores.
"""
from __future__ import annotations

import re

MAFIA = {'MAFIA_BOSS', 'MAFIA_DEPUTY'}
DIALOGUE = {'PLAYER_SPOKE', 'PLAYER_ASKED', 'PLAYER_ANSWERED'}


def public_events(observation):
    return [e for e in observation.events if e.get('visibility') == 'PUBLIC']


def normalize(text):
    return ' '.join(re.findall(r'\w+', text.casefold().replace('ي', 'ی').replace('ك', 'ک')))


def dossier(observation):
    events = public_events(observation)
    known = observation.public_state.get('revealed_roles', {})
    votes = [e for e in events if e['type'] == 'VOTE_CAST']
    reveals = []
    for index, event in enumerate(events):
        if event['type'] == 'ROLE_REVEALED' or (event['type'] == 'NIGHT_RESULT' and event.get('revealed_role')):
            pid = event.get('player')
            reveals.append({'player': pid, 'role': event.get('role', event.get('revealed_role')),
                'revealed_at': event.get('event_id'),
                'prior_votes': [v for v in votes if v in events[:index] and pid in (v.get('actor'), v.get('target'))],
                'prior_statements': [e for e in events[:index] if e['type'] in DIALOGUE and e.get('actor') == pid],
                'interpretation': 'A revealed citizen/detective could be mistaken before obtaining information. Reassess these votes; do not treat every prior suspicion as an investigation.'})
    players = {}
    for pid in observation.public_state['players']:
        history = [v for v in votes if v.get('actor') == pid]
        comparisons = []
        for vote in history:
            same = [v['actor'] for v in votes if v['round'] == vote['round'] and v['target'] == vote['target']]
            comparisons.append({'round': vote['round'], 'target': vote['target'], 'event_id': vote.get('event_id'),
                'all_voters_for_same_target': same,
                'now_revealed_citizens_in_group': [p for p in same if p in known and known[p] not in MAFIA],
                'now_revealed_mafia_in_group': [p for p in same if known.get(p) in MAFIA],
                'target_role_now': known.get(vote['target']),
                'warning': 'Shared votes are weak associations. Voting against an unconfirmed player is not evidence of guilt. Voting against revealed mafia does not clear a voter.'})
        players[pid] = {'claim': observation.public_state.get('role_claims', {}).get(pid),
            'confirmed_role': known.get(pid), 'vote_comparisons': comparisons,
            'statements': [e for e in events if e['type'] in DIALOGUE and e.get('actor') == pid][-3:]}
    ledger = []
    for question in (e for e in events if e['type'] == 'PLAYER_ASKED'):
        answers = [e for e in events if e['type'] == 'PLAYER_ANSWERED' and question.get('question_id') in
            (e.get('question_ids') or [e.get('question_id')])]
        ledger.append({'question': question, 'answers': answers,
            'status': 'answered' if answers else 'pending'})
    positions = [e for e in events if e.get('actor') == observation.player_id and e.get('position')]
    return {'candidates': [p for p in observation.public_state['alive_players'] if p != observation.player_id],
        'candidate_rule': 'Compare ALL candidates, including the questioner. A question naming A or B does not clear C.',
        'players': players, 'revelation_reviews': reveals, 'question_ledger': ledger,
        'last_public_position': positions[-1] if positions else None,
        'chronology_rule': 'Only events before a decision were available then. Night R results arrive after day R votes. A later result cannot contradict the earlier lack of information.'}


def assessment_schema(candidates, evidence_ids):
    evidence = {'type': 'array', 'maxItems': 4, 'items': {'type': 'string', **({'enum': evidence_ids} if evidence_ids else {})}}
    properties = {
        'candidates': {'type': 'array', 'minItems': len(candidates), 'maxItems': len(candidates), 'items': {
            'type': 'object', 'additionalProperties': False,
            'properties': {'player_id': {'type': 'string', 'enum': candidates},
                'support': evidence, 'counterevidence': evidence,
                'basis': {'type': 'string', 'enum': ['confirmed_role', 'reported_result', 'contradiction', 'vote_pattern', 'insufficient']},
                'explanation': {'type': 'string', 'maxLength': 160}},
            'required': ['player_id', 'support', 'counterevidence', 'basis', 'explanation']}},
        'suspect': {'type': ['string', 'null'], 'enum': [*candidates, None]},
        'reason': {'type': 'string', 'maxLength': 160, 'description': 'A short public justification in the selected language, not private reasoning. Cite events only in support/counterevidence, not in this text.'},
        'change_reason': {'type': 'string', 'maxLength': 160},
        'question_topic': {'type': 'string', 'enum': ['investigation_result', 'vote_reason', 'clarification', 'other']},
        'question_round': {'type': ['integer', 'null']},
    }
    return {'type': 'object', 'additionalProperties': False, 'properties': properties, 'required': list(properties)}


def validate_assessment(value, observation):
    if not isinstance(value, dict):
        raise ValueError('assessment_not_object')
    candidates = set(observation.public_state['alive_players']) - {observation.player_id}
    rows = value.get('candidates', [])
    if len(rows) != len(candidates) or {r.get('player_id') for r in rows} != candidates:
        raise ValueError('assessment_must_compare_all_candidates')
    by_id = {e['event_id']: e for e in public_events(observation) if e.get('event_id')}
    for row in rows:
        if row.get('basis') not in {'confirmed_role', 'reported_result', 'contradiction', 'vote_pattern', 'insufficient'}:
            raise ValueError('unsupported_evidence_basis')
        ids = [*row.get('support', []), *row.get('counterevidence', [])]
        if any(eid not in by_id for eid in ids):
            raise ValueError('assessment_cites_unavailable_evidence')
        sources = [by_id[eid] for eid in row.get('support', [])]
        if row.get('basis') == 'vote_pattern' and any(e['type'] != 'VOTE_CAST' for e in sources):
            raise ValueError('vote_pattern_requires_votes')
        if row.get('basis') == 'reported_result' and not any(e['type'] in {'PLAYER_SPOKE', 'PLAYER_ANSWERED'} for e in sources):
            raise ValueError('reported_result_requires_public_statement')
        if row.get('basis') == 'contradiction' and sources:
            before = any(re.search(r'ندار|نبود|no (?:result|evidence)|kein.*ergebnis', e.get('text',''), re.I) for e in sources)
            after = any(re.search(r'استعلام|investigat|ermittl', e.get('text',''), re.I) for e in sources)
            if before and after and len({e.get('round') for e in sources}) > 1:
                raise ValueError('later_investigation_is_not_earlier_contradiction')
        if row.get('basis') == 'confirmed_role' and not any(e.get('player') == row['player_id'] and (e['type'] == 'ROLE_REVEALED' or e.get('revealed_role')) for e in sources):
            raise ValueError('claim_is_not_confirmed_role')
        if row.get('basis') == 'confirmed_role' and row['player_id'] not in observation.public_state.get('revealed_roles', {}):
            raise ValueError('claim_is_not_confirmed_role')
        if row.get('basis') == 'contradiction' and len(set(row.get('support', []))) < 2:
            raise ValueError('contradiction_requires_two_sources')
        if row.get('basis') != 'insufficient' and not row.get('support'):
            raise ValueError('assertion_requires_evidence')
    if value.get('suspect') is not None and value['suspect'] not in candidates:
        raise ValueError('assessment_suspect_not_candidate')
    return by_id
