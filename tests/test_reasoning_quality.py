"""Behavioral regressions from game_6c2a77e52dc5, not a live-model benchmark."""
from copy import deepcopy
import json
import pytest
from app.ai.agent import AIAgent, AgentDecision
from app.ai.evidence import dossier, validate_assessment
from app.ai.reasoning import checked_decision, clean_text
from app.ai.runner import HeadlessGameRunner
from app.engine import GameEngine
from app.domain import PlayerType, Phase, Role, RuleViolation


class Provider:
    async def generate_json(self, **kwargs):
        return self.result


def setup():
    engine = GameEngine()
    game = engine.create_game([PlayerType.AI]*7, fixed_roles=[Role.MAFIA_DEPUTY, Role.DETECTIVE, Role.CITIZEN, Role.CITIZEN, Role.DOCTOR, Role.CITIZEN, Role.MAFIA_BOSS])
    game.phase = Phase.DAY_DISCUSSION; game.round = 4
    game.players['P2'].alive = game.players['P5'].alive = game.players['P6'].alive = game.players['P7'].alive = False
    engine._event(game, 'ROLE_REVEALED', {'player':'P7','role':'MAFIA_BOSS'})
    game.discussion_order = ['P3','P4','P1']
    runner = HeadlessGameRunner(engine, game, {})
    provider = Provider()
    agent = AIAgent('P3', provider, player_names={'P1':'Matteo Ricci','P3':'Rosa Greco','P4':'Marco Conti'})
    return engine, game, runner, agent, provider


def event(engine, game, kind, **payload):
    engine._event(game, kind, payload)
    return game.events[-1].event_id


def plan(obs, suspect='P4', support=None, basis='insufficient'):
    return {'candidates':[{'player_id':pid,'support':support or [],'counterevidence':[], 'basis':basis,'explanation':'Public evidence remains uncertain.'}
        for pid in obs.public_state['alive_players'] if pid != obs.player_id],
        'suspect':suspect,'reason':'این ارزیابی قطعی نیست.', 'change_reason':'', 'question_topic':'other','question_round':None}


def vote():
    return AgentDecision('SUBMIT_VOTE_DECISION', {'vote_target':'P1','trusted_player':'P4'})


def test_changed_opinion_is_not_overridden_even_without_new_evidence():
    engine, game, runner, agent, _ = setup()
    event(engine, game, 'PLAYER_SPOKE', actor='P3', text='Marco is suspicious.',
          position={'target':'P4','reason':'A hypothesis','evidence_ids':[]})
    obs = runner.observation('P3', ['SUBMIT_VOTE_DECISION'])
    result = checked_decision(agent, vote(), {}, obs)
    assert result.payload == vote().payload
    game.phase = Phase.DAY_VOTING
    engine.submit_action(game, 'P3', result.action, result.payload)
    assert game.vote_decisions['P3'].vote_target == 'P1'


def test_all_candidates_including_questioner_must_be_compared():
    _,_,runner,agent,_=setup(); obs=runner.observation('P3',['ANSWER'])
    data=plan(obs); data['candidates']=[data['candidates'][1]]
    with pytest.raises(ValueError,match='all_candidates'): validate_assessment(data,obs)
    assert dossier(obs)['candidates']==['P1','P4']


def test_reveal_reconsiders_all_matching_votes_without_clearing_a_bus_vote():
    engine,game,runner,agent,_=setup()
    game.events = game.events[:2]
    game.round=1
    for actor,target in [('P1','P2'),('P7','P2'),('P2','P1'),('P6','P1')]: event(engine,game,'VOTE_CAST',actor=actor,target=target)
    game.round=2
    event(engine,game,'VOTE_CAST',actor='P1',target='P7')
    event(engine,game,'ROLE_REVEALED',player='P7',role='MAFIA_BOSS')
    event(engine,game,'ROLE_REVEALED',player='P2',role='DETECTIVE')
    event(engine,game,'NIGHT_RESULT',player='P2',revealed_role='DETECTIVE',result='PLAYER_KILLED')
    book=dossier(runner.observation('P3'))
    isabella=book['players']['P6']['vote_comparisons'][0]
    assert isabella['all_voters_for_same_target']==['P2','P6']
    assert isabella['now_revealed_citizens_in_group']==['P2']
    matteo=book['players']['P1']['vote_comparisons']
    assert matteo[0]['now_revealed_mafia_in_group']==['P7']
    assert matteo[1]['target_role_now']=='MAFIA_BOSS'
    assert 'does not clear' in matteo[1]['warning']
    assert any(r['player']=='P2' and r['prior_votes'] for r in book['revelation_reviews'])


def test_private_or_fabricated_evidence_is_never_published():
    engine,game,runner,agent,_=setup()
    engine._event(game,'INVESTIGATION_RESULT',{'player':'P3','target':'P1','result':'MAFIA_DEPUTY'},'PRIVATE','P3')
    obs=runner.observation('P3')
    for eid in [game.events[-1].event_id,'evt_fake']:
        with pytest.raises(ValueError,match='unavailable_evidence'): validate_assessment(plan(obs,support=[eid]),obs)
    assert 'INVESTIGATION_RESULT' not in json.dumps(dossier(obs))


def test_role_claim_cannot_be_used_as_confirmed_identity():
    engine,game,runner,_,_=setup()
    eid=event(engine,game,'ROLE_CLAIMED',actor='P1',claimed_role='CITIZEN')
    with pytest.raises(ValueError,match='not_confirmed'): validate_assessment(plan(runner.observation('P3'),support=[eid],basis='confirmed_role'),runner.observation('P3'))


def test_later_investigation_does_not_contradict_previous_lack_of_evidence():
    engine,game,runner,_,_=setup();game.round=1
    before=event(engine,game,'PLAYER_SPOKE',actor='P2',text='فعلاً نتیجه‌ای ندارم.')
    game.round=2;after=event(engine,game,'PLAYER_SPOKE',actor='P2',text='استعلام شب اول مافیا بود.')
    obs=runner.observation('P3')
    with pytest.raises(ValueError,match='earlier_contradiction'): validate_assessment(plan(obs,support=[before,after],basis='contradiction'),obs)


def test_legal_dialogue_is_not_replaced_with_canned_text_or_silence():
    engine, game, runner, agent, _ = setup()
    event(engine, game, 'PLAYER_SPOKE', actor='P1', text='A repeated claim.')
    obs = runner.observation('P3', ['SPEAK','ASK','PASS'])
    for statement in ['A repeated claim.', 'Definitely Mafia.', 'I am unsure.']:
        decision = AgentDecision('SPEAK', {'text': statement})
        assert checked_decision(agent, decision, {}, obs) == decision


@pytest.mark.parametrize('language',['fa','en','de'])
def test_technical_event_ids_and_role_codes_are_localized(language):
    value=clean_text('evt_000053 MAFIA_BOSS MAFIA_DEPUTY DOCTOR DETECTIVE CITIZEN',language)
    assert 'evt_' not in value and 'MAFIA_' not in value and 'DETECTIVE' not in value


def test_beliefs_do_not_drift_on_repeated_observation_and_known_roles_cannot_be_overwritten():
    engine,game,runner,agent,_=setup();obs=runner.observation('P3')
    agent._initialize_beliefs(obs);before=dict(agent.state.beliefs)
    for _ in range(8): agent._initialize_beliefs(obs)
    assert agent.state.beliefs==before
    obs.private_state['investigations']=[{'target':'P1','result':'MAFIA_DEPUTY','round':1}]
    agent._apply_agent_state({'belief_updates':{'P1':0.01}},obs)
    assert agent.state.beliefs['P1']==1


def test_engine_rejects_private_evidence_before_mutating_discussion():
    engine,game,runner,_,_=setup()
    before=len(game.events)
    with pytest.raises(RuleViolation): engine.submit_action(game,'P3','SPEAK',{'text':'test', 'position':{'target':'P1','reason':'test','evidence_ids':['private-id']}})
    assert len(game.events)==before and game.discussion_index==0


@pytest.mark.anyio
async def test_live_schema_does_not_require_an_assessment():
    _, _, runner, agent, provider = setup()
    obs = runner.observation('P3', ['SPEAK','PASS'])
    provider.result = {'action':'SPEAK','text':'در evt_000053 نقش MAFIA_BOSS مطرح شده است.', 'referenced_players':[]}
    result = await agent.decide(obs)
    assert result.source == 'model'
    assert 'evt_' not in result.payload['text']
    assert 'assessment' not in agent._decision_schema(obs)['properties']
    context = json.loads(agent._user_prompt(obs))
    assert context['optional_library']['optional']
    assert 'distance' not in {c['id'] for c in context['optional_library']['cards']}


@pytest.mark.anyio
async def test_five_offline_matches_finish_with_optional_votes():
    from app.ai.service import build_runner
    for seed in range(5):
        engine = GameEngine()
        game = engine.create_game([PlayerType.AI]*7, seed=seed)
        runner = build_runner(engine, game, mode='offline', settings=None, live_action_budget=0)
        await runner.run()
        assert game.phase == Phase.GAME_OVER
