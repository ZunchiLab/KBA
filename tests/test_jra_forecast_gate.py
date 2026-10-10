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
    def test_missing_alternate_scenario_fails(self):
        p=fixture();p['races'][0]['analysis']['preflight_review']['scenario_checks'].pop();self.assertIn('scenario_ticket_audit_missing',self.codes(p))
    def test_repeated_evidence_and_cost_error_fail(self):
        p=fixture();h=p['races'][0]['horses'][0];h['evaluated_runs']*=2;p['budget']['selected_main_yen']=200;self.assertTrue({'duplicate_scored_run','budget_mismatch'}<=self.codes(p))
if __name__=='__main__':unittest.main()
