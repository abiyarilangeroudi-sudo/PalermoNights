"""Isolated real-browser fixtures; never imported by the production application."""
import json
import re
from pathlib import Path
from fastapi.responses import HTMLResponse, Response
from app.main import app, engine
from app.domain import PlayerType, Phase

ROOT = Path(__file__).resolve().parents[2]
create = engine.create_game
engine.create_game = lambda kinds: create(kinds, seed=12)


@app.get('/browser-fixture')
def fixture(view: str = 'vote'):
    html = (ROOT / 'Frontend/index.html').read_text()
    return HTMLResponse(re.sub(r'/ui/app\.js\?[^"\s]+', f'/browser-fixture.js?view={view}', html))


@app.get('/browser-fixture.js')
def script(view: str = 'vote'):
    code = (ROOT / 'Frontend/app.js').read_text()
    code = code[:code.rfind('$("#new-game").addEventListener')]
    game = engine.create_game([PlayerType.HUMAN] * 7)
    game.phase = Phase.DAY_VOTING if view == 'vote' else Phase.DAY_DISCUSSION
    game.round = 2
    code += '\nconst fixture=' + json.dumps(engine.public_state(game)) + ';\n'
    code += '''
state.gameId='browser-fixture'; state.token='fixture-token'; state.playerId='P1'; state.characterId=1;
state.public=fixture; state.events=[]; state.characterMap=buildCharacterMap(1);
state.private={role:'DOCTOR',faction:'CITIZEN',trust:{},investigations:[]};
state.run={status:'WAITING_FOR_HUMAN',mode:'offline'};
state.drafts=readStored(SESSION_KEY,{})?.drafts || {};
setLanguage('fa'); showScreen('story-screen');
$$('[data-go-home]').forEach(b=>b.addEventListener('click',goHome));
$('#resume-game').addEventListener('click',restoreSession);
'''
    if view == 'vote':
        code += "state.availableActions=['SUBMIT_VOTE_DECISION']; showVote();"
    elif view == 'answer':
        code += """state.events=[{type:'PLAYER_ASKED',actor:'P2',target:'P1',question_id:'q1',event_id:'q1',text:'سؤال بلند '.repeat(100)},
        {type:'PLAYER_ASKED',actor:'P3',target:'P1',question_id:'q2',event_id:'q2',text:'دلیل رأی قبلی خود را توضیح بده. '.repeat(80)}];
        state.availableActions=['ANSWER']; showHumanDiscussion(['ANSWER']);"""
    else:
        code += "state.availableActions=['SPEAK','ASK','PASS']; showHumanDiscussion(state.availableActions);"
    code += '\nwindow.fixtureReady=true;'
    return Response(code, media_type='application/javascript')
