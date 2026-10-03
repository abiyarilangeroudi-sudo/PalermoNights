"""Read-only visual QA with saved public events. No game or model requests."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from fastapi.responses import HTMLResponse, Response
from app.main import app


@app.get('/journal-preview', include_in_schema=False)
def preview():
    html = (ROOT / 'Frontend/index.html').read_text()
    return HTMLResponse(html.replace('/ui/app.js?v=20261013', '/journal-preview.js'))


@app.get('/journal-preview.js', include_in_schema=False)
def preview_script():
    code = (ROOT / 'Frontend/app.js').read_text()
    code = code[:code.rfind('$("#new-game").addEventListener')]
    fixture = json.loads(Path(__file__).with_name('game_4c9cb8007e61-public-review.json').read_text())
    data = json.dumps(fixture, ensure_ascii=False)
    code += '\nconst fixture = ' + data + ';\n' + '''
state.lang='fa'; document.documentElement.lang='fa'; document.documentElement.dir='rtl';
state.public=fixture['public-state']; state.events=fixture.events.events;
state.private={role:'DOCTOR', trust:{}, investigations:[]};
state.characterMap=buildCharacterMap(1); state.consoleTab='timeline';
state.nightReplay=[];
showScreen('story-screen'); renderFacts(); setFactsOpen(true);
$$('[data-console-tab]').forEach(button=>button.addEventListener('click',()=>{
  state.consoleTab=button.dataset.consoleTab; renderFacts();
}));
'''
    return Response(code, media_type='application/javascript')


@app.get('/answer-preview', include_in_schema=False)
def answer_preview():
    html = (ROOT / 'Frontend/index.html').read_text()
    return HTMLResponse(html.replace('/ui/app.js?v=20261013', '/answer-preview.js'))


@app.get('/discussion-preview', include_in_schema=False)
def discussion_preview():
    return answer_preview()


@app.get('/answer-preview.js', include_in_schema=False)
def answer_preview_script():
    code = (ROOT / 'Frontend/app.js').read_text()
    code = code[:code.rfind('$("#new-game").addEventListener')]
    fixture = json.loads(Path(__file__).with_name('game_4c9cb8007e61-public-review.json').read_text())
    public = json.dumps(fixture['public-state'], ensure_ascii=False)
    code += '\nconst previewPublic = ' + public + ';\n' + '''
state.lang='fa'; document.documentElement.lang='fa'; document.documentElement.dir='rtl';
state.public={...previewPublic,round:2,phase:'DAY_DISCUSSION'};
state.private={role:'DOCTOR',faction:'CITIZEN',trust:{},investigations:[]};
state.characterMap=buildCharacterMap(1);
state.events=[
  {type:'PLAYER_ASKED',round:2,visibility:'PUBLIC',actor:'P4',target:'P1',question_id:'q1',text:'چرا در دور نخست به النا رأی دادی و در دور دوم نظرت را دربارهٔ روزا تغییر دادی؟ استدلالت را با توجه به رأی‌های دیگران توضیح بده.'},
  {type:'PLAYER_ASKED',round:2,visibility:'PUBLIC',actor:'P5',target:'P1',question_id:'q2',text:'برای هر دو رأی خود چه مدرکی داشتی؟ آیا گفته‌های ویتوریو را هم در تصمیم نهایی‌ات بررسی کردی؟ لطفاً دلیل خود را روشن و کامل بنویس.'},
  {type:'PLAYER_ASKED',round:2,visibility:'PUBLIC',actor:'P6',target:'P1',question_id:'q3',text:'اگر اطلاعات جدیدی دربارهٔ نقش روزا داری، بگو کدام بخش از رفتار او نظرت را تغییر داد و چرا این موضوع در دور قبل برایت روشن نبود؟'},
  {type:'PLAYER_ASKED',round:2,visibility:'PUBLIC',actor:'P7',target:'P1',question_id:'q4',text:'آیا هنوز به تحلیل دیروزت پایبندی؟ لطفاً ترتیب رخدادها و رأی‌هایی را که برای تصمیم امروزت مهم بوده‌اند مشخص کن.'}
];
submitAndAdvance=async()=>{}; // Visual QA only: never send a game action.
showScreen('story-screen'); showHumanDiscussion(window.location.pathname === '/discussion-preview' ? ['SPEAK','ASK','PASS'] : ['ANSWER']);
'''
    return Response(code, media_type='application/javascript')


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=8021, log_level='warning')
