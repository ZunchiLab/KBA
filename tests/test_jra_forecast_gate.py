import json,sys,unittest
from pathlib import Path
from copy import deepcopy
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from check_jra_forecast import audit

def fixture():
    horses=[dict(number=n,rank=n,model_rank=n,score_method='single_pass_past_comparison',market={'win':float(n+1)},evidence_refs=['run'+str(n)],evaluated_runs=[dict(run_id='run'+str(n),resolved_class='1勝クラス')],past=[dict(run_id='run'+str(n),finish=n,distance=1800,class_adjustment=0,resolved_class='1勝クラス')]) for n in [1,2]]
    review={'single_win_edge':{'number':1,'rival_numbers':[2],'why_win_not_only_place':'Fixture comparison of winning evidence','evidence_refs':['run1','run2']},'exclusions':[{'number':2,'compared_with':[1],'reason':'Fixture relative comparison','evidence_refs':['run1','run2']}],'scenario_checks':[{'scenario':s,'response':'keep','reason':'Fixture scenario review','evidence_refs':['run1','run2']} for s in ['main','alternate']],'fact_checks':[{'number':1,'run_id':'run1','field':'resolved_class','expected':'1勝クラス'}]}
    return dict(authority='jra',document_type='prediction',fixed_at='2026-10-11T09:00:00+09:00',budget={'selected_main_yen':100},races=[dict(race_uid='test',start_at='2026-10-11T10:00:00+09:00',distance_m=1800,horses=horses,analysis={'win_candidates':[1,2],'place_candidates':[1,2],'preflight_review':review},bet_plans=[dict(kind='win',selected_for_example=True,tickets=[dict(numbers=[1],example_stake_yen=100)])])])

class Gate(unittest.TestCase):
    def codes(self,p):return {x['code'] for x in audit(p,True)}
    def test_explicit_comparisons_pass(self):self.assertEqual(audit(fixture(),True),[])
    def test_stability_only_cannot_authorize_single_win(self):
        p=fixture();del p['races'][0]['analysis']['preflight_review']['single_win_edge'];self.assertIn('single_win_edge_missing',self.codes(p))
    def test_unknown_opponent_cannot_be_silently_relegated(self):
        p=fixture();p['races'][0]['horses'][1]['score_method']='insufficient_evidence';self.assertIn('uncertainty_not_resolved',self.codes(p))
    def test_own_evidence_alone_is_not_direct_comparison(self):
        p=fixture();p['races'][0]['analysis']['preflight_review']['exclusions'][0]['evidence_refs']=['run2'];self.assertIn('opponent_comparison_missing',self.codes(p))
        p=fixture();r=p['races'][0];h=deepcopy(r['horses'][1]);h.update(number=3,rank=3,model_rank=3,evidence_refs=['run3']);h['past'][0]['run_id']='run3';h['evaluated_runs'][0]['run_id']='run3';r['horses'].append(h);r['analysis']['win_candidates'].append(3);r['analysis']['preflight_review']['single_win_edge']['rival_numbers'].append(3)
        self.assertIn('single_win_edge_missing',self.codes(p)) # Naming a second rival without its evidence is insufficient.
    def test_wrong_grade_fails(self):
        p=fixture();p['races'][0]['analysis']['preflight_review']['fact_checks'][0]['expected']='2勝クラス';self.assertIn('source_claim_mismatch',self.codes(p))
    def test_stale_market_reference_rank_fails(self):
        p=fixture();hs=p['races'][0]['horses'];hs[0]['score_method']=hs[1]['score_method']='market_reference';hs[0]['market']['win']=9.;self.assertIn('market_reference_order_stale',self.codes(p))
    def test_withdrawn_debut_runner_has_no_reference_rank(self):
        p=fixture();r=p['races'][0];r['bet_plans']=[];p['budget']['selected_main_yen']=0
        for h in r['horses']:h['score_method']='market_reference';h['status_at_snapshot']='declared'
        r['horses'][1].update(status_at_snapshot='withdrawn',rank=None,market={'win':None})
        self.assertEqual(audit(p,True),[])
        r['horses'][0]['rank']=2
        self.assertIn('market_reference_order_stale',self.codes(p))
    def test_new_main_requires_pre_race_official_listed_history(self):
        p=fixture();p['date_jst']='2026-10-17';p['fixed_at']='2026-10-17T09:00:00+09:00';p['races'][0]['start_at']='2026-10-17T10:00:00+09:00'
        self.assertIn('listed_history_scope_missing',self.codes(p))
        for h in p['races'][0]['horses']:
            h['history_audit']=dict(status='parsed',summary='Fixture listed-history scope',source=dict(provider='JRA',url='https://jra.jp/JRADB/accessU.html?CNAME=fixture',retrieved_at='2026-10-17T08:59:00+09:00',raw_sha256='a'*64))
        self.assertNotIn('listed_history_scope_missing',self.codes(p))
        p['races'][0]['horses'][1]['history_audit']['source']['retrieved_at']='2026-10-17T09:01:00+09:00'
        self.assertIn('listed_history_scope_missing',self.codes(p))
    def test_missing_alternate_scenario_fails(self):
        p=fixture();p['races'][0]['analysis']['preflight_review']['scenario_checks'].pop();self.assertIn('scenario_ticket_audit_missing',self.codes(p))
    def test_repeated_evidence_and_cost_error_fail(self):
        p=fixture();h=p['races'][0]['horses'][0];h['evaluated_runs']*=2;p['budget']['selected_main_yen']=200;self.assertTrue({'duplicate_scored_run','budget_mismatch'}<=self.codes(p))
    def counterpart_fixture(self):
        p=fixture();p['date_jst']='2026-10-12';p['fixed_at']='2026-10-12T09:00:00+09:00';r=p['races'][0];r['start_at']='2026-10-12T10:00:00+09:00'
        for n in [3,4,5]:
            h=deepcopy(r['horses'][1]);h.update(number=n,rank=n,model_rank=n,market={'win':2.5 if n==5 else float(n+1)},evidence_refs=['run'+str(n)])
            h['past'][0].update(run_id='run'+str(n),finish=n);h['evaluated_runs'][0]['run_id']='run'+str(n);r['horses'].append(h)
        r['bet_plans']=[dict(plan_id='q',kind='quinella',groups=[[1,2],[1,2,3,4]],selected_for_example=True,tickets=[dict(numbers=list(t),example_stake_yen=100) for t in [(1,2),(1,3),(1,4),(2,3),(2,4)]])];p['budget']['selected_main_yen']=500
        r['analysis']['formation_review']={'plans':[{'linked_plan_id':'q','counterpart_exclusions':[]}]}
        return p
    def test_new_omitted_popular_counterpart_requires_its_own_comparison(self):
        p=self.counterpart_fixture();self.assertIn('counterpart_slot_comparison_missing',self.codes(p))
        e={'number':5,'compared_with':[1],'reason':'Only compared against axis','evidence_refs':['run1','run5']};p['races'][0]['analysis']['formation_review']['plans'][0]['counterpart_exclusions']=[e]
        self.assertIn('counterpart_slot_comparison_missing',self.codes(p))
        e.update(compared_with=[4],evidence_refs=['run4','run5']);self.assertEqual(audit(p,True),[])
    def test_counterpart_comparison_needs_evidence_from_both_horses(self):
        p=self.counterpart_fixture();p['races'][0]['analysis']['formation_review']['plans'][0]['counterpart_exclusions']=[{'number':5,'compared_with':[4],'reason':'Comparison','evidence_refs':['run5']}]
        self.assertIn('counterpart_slot_comparison_missing',self.codes(p))
    def test_condition_return_candidate_outside_top_four_is_reviewed(self):
        p=self.counterpart_fixture();h=p['races'][0]['horses'][-1];h['market']['win']=90.;h['condition_return_candidate']=True
        self.assertIn('counterpart_slot_comparison_missing',self.codes(p))
    def test_existing_forecast_and_unselected_plan_keep_their_contract(self):
        p=self.counterpart_fixture();p['date_jst']='2026-10-11';p['fixed_at']='2026-10-11T09:00:00+09:00';self.assertEqual(audit(p,True),[])
        p=self.counterpart_fixture();p['races'][0]['bet_plans'][0]['selected_for_example']=False;p['budget']['selected_main_yen']=0;self.assertEqual(audit(p,True),[])
if __name__=='__main__':unittest.main()
