"""Isolated UI fixture for review; no game creation or model requests."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from fastapi.responses import HTMLResponse, Response
from app.main import app

@app.get('/review')
def page(view: str = 'journal'):
    html = (ROOT / 'Frontend/index.html').read_text()
    return HTMLResponse(re.sub(r'/ui/app\.js\?[^"\s]+', f'/review.js?view={view}', html))

@app.get('/review.js')
def script(view: str = 'journal'):
    code = (ROOT / 'Frontend/app.js').read_text()
    code = code[:code.rfind('$("#new-game").addEventListener')]
    fixture = json.loads((ROOT / 'audit/2026-10-02/live-luna/game_4c9cb8007e61-public-review.json').read_text())
    code += '\nconst fixture=' + json.dumps(fixture, ensure_ascii=False) + ';\n'
    code += '''
state.lang='fa'; document.documentElement.lang='fa'; document.documentElement.dir='rtl';
state.public=fixture['public-state']; state.events=fixture.events.events;
state.private={role:'DOCTOR',faction:'CITIZEN',trust:{},investigations:[]};
state.characterMap=buildCharacterMap(1); state.run={status:'WAITING_FOR_HUMAN'};
submitAndAdvance=async()=>{};
showScreen('story-screen');
'''
    if view == 'journal':
        code += "renderFacts(); setFactsOpen(true);"
    elif view == 'vote':
        code += "state.public.round=2; showVote();"
    else:
        code += "showHumanDiscussion(['SPEAK','ASK','PASS']);"
    return Response(code, media_type='application/javascript')

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=8022, log_level='warning')
