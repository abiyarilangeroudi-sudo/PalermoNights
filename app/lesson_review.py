"""Review a completed case into an optional, versioned reference card.

python -m app.lesson_review --database PATH --game-id ID --card reviewed-card.json
The card needs title, observation, hypothesis, counterexample and limitations.
"""
import argparse
import json
from pathlib import Path
from .persistence import SnapshotStore
from .ai.library import VERSION


def reviewed_card(case, card):
    if not case.get('complete'):
        raise ValueError('Only completed games can become strategic reference cases')
    fields = ('title', 'observation', 'hypothesis', 'counterexample', 'limitations')
    if any(not isinstance(card.get(k), str) or not 1 <= len(card[k].strip()) <= 1200 for k in fields):
        raise ValueError('Each review field must contain 1–1200 characters')
    return {'version': VERSION, 'status': 'reviewed', 'source_game': case['game_id'],
            **{k: card[k].strip() for k in fields}}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True)
    parser.add_argument('--game-id', required=True)
    parser.add_argument('--card', required=True)
    args=parser.parse_args()
    store=SnapshotStore(args.database);store.open()
    try:
        case=next(c for c in store.lessons() if c['game_id']==args.game_id)
        result=reviewed_card(case,json.loads(Path(args.card).read_text()))
        # A stopped local server is required by the store's single-writer lock.
        case['review']=result
        with store.lock, store.connection:
            store.connection.execute('UPDATE lessons SET body=? WHERE id=?',(json.dumps(case,ensure_ascii=False),args.game_id))
        print('Reviewed lesson saved:',args.game_id)
    finally: store.close()

if __name__=='__main__': main()
