"""Checks for grounded, chronological and publicly accountable decisions."""
from dataclasses import replace
import re
from .evidence import dossier, public_events, normalize, validate_assessment, DIALOGUE


def clean_text(value, language):
    roles = {
        'fa': ['رئیس مافیا', 'معاون مافیا', 'کارآگاه', 'پزشک', 'شهروند'],
        'en': ['Mafia boss', 'Mafia deputy', 'detective', 'doctor', 'citizen'],
        'de': ['Mafia-Boss', 'Mafia-Stellvertreter', 'Detektiv', 'Arzt', 'Bürger'],
    }[language]
    for role, label in zip(['MAFIA_BOSS','MAFIA_DEPUTY','DETECTIVE','DOCTOR','CITIZEN'], roles):
        value = re.sub(r'\b' + role + r'\b', label, value)
    label = {'fa': 'رویداد ثبت‌شده', 'en': 'the recorded event', 'de': 'das protokollierte Ereignis'}[language]
    return re.sub(r'\bevt_[A-Za-z0-9_]+\b', label, value)


def checked_decision(agent, decision, result, observation):
    """Validate legal fields without substituting the player's strategic judgment."""
    payload = dict(decision.payload)
    if isinstance(payload.get('text'), str):
        payload['text'] = clean_text(payload['text'], agent.language)
    decision = replace(decision, payload=payload)
    return agent._validate_targets(decision, observation)
