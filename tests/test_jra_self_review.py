import copy,math,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from jra_role_indices import apply_indices,audit_indices,ROLES
from jra_decision_review import audit_race
from test_jra_role_indices import race,past,ASOF

class ReliabilityTests(unittest.TestCase):
    def calculate(self,r):return apply_indices(r,as_of=ASOF,computed_at=ASOF)
    def test_single_runner_up_is_not_full_marks(self):
        d=self.calculate(race())['horses'][1]['role_indices']
        self.assertEqual(d['second']['raw_value'],100)
        self.assertLess(d['second']['value'],60)
        self.assertLess(d['reliability_weight'],.25)
    def test_repeated_support_changes_strength_not_just_the_display_scale(self):
        r=race();r['horses'][1]['past']=[past(2,day=f'2026-10-{day:02}',rid=f'x-{day}') for day in [20,16,12,8]]
        repeated=self.calculate(r)['horses'][1]['role_indices'];single=self.calculate(race())['horses'][1]['role_indices']
        self.assertGreater(repeated['reliability_weight'],single['reliability_weight'])
        self.assertGreater(repeated['second']['value'],single['second']['value'])
    def test_reference_normalization_does_not_undo_single_run_suppression(self):
        r=self.calculate(race())
        self.assertTrue(all(40<h['role_indices'][k]['value']<60 for h in r['horses'] for k in ROLES))
    def test_identical_profiles_get_reference_50_not_top_marks(self):
        r=race()
        for h in r['horses']:h['past']=[past(2,rid=str(h['number']))]
        d=self.calculate(r)
        self.assertTrue(all(h['role_indices'][k]['value']==50 for h in d['horses'] for k in ROLES))
    def test_same_horse_changes_relative_index_when_opponents_change(self):
        a=self.calculate(race())['horses'][0]['role_indices'];r=race()
        for h in r['horses'][1:]:h['past']=[past(1,rid='other-'+str(h['number']))]
        b=self.calculate(r)['horses'][0]['role_indices']
        self.assertEqual(a['first']['raw_value'],b['first']['raw_value'])
        self.assertGreater(a['first']['value'],b['first']['value']);self.assertEqual(b['first']['value'],50)
    def test_old_information_reduces_extremeness_not_automatic_inferiority(self):
        r=race();r['horses'][1]['past'][0]['iso_date']='2025-10-20'
        d=self.calculate(r)['horses'][1]['role_indices'];fresh=self.calculate(race())['horses'][1]['role_indices']
        self.assertLess(d['reliability_weight'],fresh['reliability_weight'])
        self.assertLess(abs(d['second']['value']-50),abs(fresh['second']['value']-50))
    def test_nan_infinity_boolean_and_negative_losing_margin_not_scored(self):
        for bad in [math.nan,math.inf,-math.inf,True,-.1]:
            r=race();r['horses'][1]['past'][0]['gap']=bad
            d=self.calculate(r)['horses'][1]['role_indices']
            self.assertEqual(d['method'],'not_computed');self.assertIsNone(d['first']['value'])
    def test_false_history_cannot_promote_selected_old_good_runs(self):
        with self.assertRaises(ValueError):apply_indices(race(),as_of=ASOF,history_by_number={1:dict(status='error',prior_races=[],source=dict(retrieved_at=ASOF))})
    def test_later_class_resolution_is_not_available_at_input_cutoff(self):
        r=race();r['horses'][0]['past'][0]['class_source']=dict(retrieved_at='2026-11-01T09:00:00+09:00')
        with self.assertRaises(ValueError):self.calculate(r)
    def test_wrong_runner_history_is_rejected(self):
        with self.assertRaises(ValueError):apply_indices(race(),as_of=ASOF,history_by_number={1:dict(status='parsed',prior_races=[],number=2)})
    def test_gate_rejects_missing_role_keys_duplicate_evidence_and_market_copies(self):
        r=self.calculate(race());del r['horses'][0]['role_indices']['second']
        self.assertIn('role_indices_invalid',[e[0] for e in audit_indices(r,ASOF)])
        r=self.calculate(race());r['horses'][0]['role_indices']['components']*=2
        self.assertIn('role_index_evidence_missing',[e[0] for e in audit_indices(r,ASOF)])
        r=self.calculate(race());d=r['horses'][0]['role_indices'];d.update(method='market_reference',market_reference=dict(value=3.5))
        self.assertIn('market_as_performance_index',[e[0] for e in audit_indices(r,ASOF)])

class DecisionTests(unittest.TestCase):
    def fixture(self):
        r=race();r['analysis']['role_index_usage_review']=dict(mode='auxiliary_only',benchmark_edge_unproven=True,independent_comparison_reason='実績と条件を個別比較');r['bet_plans'][0].update(kind='wide',plan_id='main');r['horses'][2]['model_rank']=3
        for h in r['horses']:h['market']=dict(win=100+h['number'])
        exclusions=[]
        for n in [3,4]:exclusions.append(dict(number=n,compared_with=[2],reason='具体的比較',best_case=dict(run_id='run-'+str(n),why_relevant='今回条件の反証'),peer_case=dict(number=2,run_id='run-2',why_prefer='今回の相手枠で比較'),evidence_refs=['run-'+str(n),'run-2']))
        r['analysis']['preflight_review']=dict(exclusions=exclusions,dependency_reviews=[dict(plan_id='main',mandatory_numbers=[1,2],without_core=[3,4],retained_reason='共通二頭が崩れる対案との比較',evidence_refs=['run-1','run-2','run-3','run-4'])])
        return r
    def test_named_best_case_and_uncovered_pair_pass_without_mutating_bets(self):
        r=self.fixture();before=copy.deepcopy(r);self.assertEqual(audit_race(r),[]);self.assertEqual(before,r)
    def test_generic_exclusion_cannot_pass_as_best_case_review(self):
        r=self.fixture();del r['analysis']['preflight_review']['exclusions'][0]['best_case']
        self.assertIn('best_counterevidence_review_missing',[e[0] for e in audit_race(r)])
    def test_best_case_must_belong_to_omitted_horse_and_peer_must_be_adopted(self):
        r=self.fixture();r['analysis']['preflight_review']['exclusions'][0]['best_case']['run_id']='run-1'
        self.assertIn('best_counterevidence_review_missing',[e[0] for e in audit_race(r)])
    def test_missing_or_fabricated_without_core_pair_fails(self):
        r=self.fixture();r['analysis']['preflight_review']['dependency_reviews']=[]
        self.assertIn('core_dependency_review_missing',[e[0] for e in audit_race(r)])
        r=self.fixture();r['analysis']['preflight_review']['dependency_reviews'][0]['without_core']=[1,3]
        self.assertIn('core_dependency_review_missing',[e[0] for e in audit_race(r)])
    def test_unbet_race_does_not_require_wager_comparison(self):
        r=race();r['bet_plans']=[];self.assertEqual(audit_race(r),[])

if __name__=='__main__':unittest.main()
