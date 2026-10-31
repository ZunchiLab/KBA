import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from jra_role_indices import apply_indices,audit_indices,ROLES,VERSION
from jra_mark_policy import apply,audit_race,COVERAGE_POLICY,suggested_limit

ASOF='2026-11-01T08:00:00+09:00'
def past(f=2,surface='芝',day='2026-10-20',rid='run-a',cl='1勝クラス'):
    return dict(iso_date=day,venue='東京',resolved_class=cl,surface=surface,distance=1600,finish=f,field=12,gap=.2,condition='良',run_id=rid)
def race():
    return dict(start_at='2026-11-01T10:00:00+09:00',venue='東京',surface='turf',distance_m=1600,class_text='1勝クラス',grade='',analysis={},bet_plans=[dict(selected_for_example=True,tickets=[dict(numbers=[1,2])])],horses=[dict(number=n,name=str(n),rank=n,score=91-n,mark='無印',status_at_snapshot='declared',score_method='independent',past=[past(n,rid='run-'+str(n))],evidence_refs=['run-'+str(n)]) for n in range(1,7)])

class RoleIndicesTest(unittest.TestCase):
    def calculate(self,r,**kw):return apply_indices(r,as_of=ASOF,computed_at=ASOF,**kw)
    def test_does_not_mutate_marks_old_scores_or_tickets(self):
        r=race();before=copy.deepcopy(r);out=self.calculate(r)
        self.assertEqual(r,before);self.assertEqual(out['bet_plans'],r['bet_plans'])
        for a,b in zip(r['horses'],out['horses']):
            self.assertEqual({k:v for k,v in b.items() if k!='role_indices'},a)
        self.assertEqual(audit_indices(out,ASOF),[])
    def test_second_is_not_top2_or_first_and_roles_have_distinct_orders(self):
        out=self.calculate(race());a,b,c=[h['role_indices'] for h in out['horses'][:3]]
        self.assertGreater(a['first']['value'],b['first']['value'])
        self.assertGreater(b['second']['value'],a['second']['value'])
        self.assertGreater(b['top2']['value'],c['top2']['value'])
        self.assertGreater(c['top3']['value'],c['top2']['value'])
        self.assertFalse(a['probability']);self.assertFalse(a['calibrated'])
    def test_old_full_history_restores_score_without_selecting_only_good_runs(self):
        r=race();h=r['horses'][0];h['past']=[past(8,'ダ')]
        rows=[dict(date=d,venue='東京',race_name='1勝クラス',grade_raw='',surface='turf',distance=1600,going='良',finish_raw=str(f),source_row=['','','','','','12'],result_url='older-'+str(f)) for d,f in [('2026-07-01',2),('2026-06-01',12)]]
        hist={1:dict(status='parsed',prior_races=rows,source=dict(retrieved_at=ASOF))}
        out=self.calculate(r,history_by_number=hist)['horses'][0]['role_indices']
        self.assertEqual(out['method'],'same_surface_history');self.assertEqual(out['runs'],2)
        self.assertEqual({x['finish'] for x in out['components']},{2,12})
    def test_cross_surface_is_explicit_reference_with_low_strength(self):
        r=race();r['horses'][0]['past']=[past(3,'ダ')]
        d=self.calculate(r)['horses'][0]['role_indices']
        self.assertEqual(d['method'],'cross_surface_reference');self.assertEqual(d['confidence'],'薄')
        self.assertTrue(all(d[k]['value'] is not None for k in ROLES))
    def test_unknown_class_is_not_zero_adjustment_or_independent_score(self):
        r=race();r['horses'][0]['past']=[past(1,cl='未確認')]
        d=self.calculate(r)['horses'][0]['role_indices']
        self.assertEqual(d['method'],'not_computed');self.assertTrue(all(d[k]['value'] is None for k in ROLES))
    def test_market_fallback_cannot_claim_independent_role_estimates(self):
        r=race();h=r['horses'][0];h['past']=[past(1,cl='JpnI')];h['market']=dict(win=2.0,source=dict(url='https://jra.jp/odds',retrieved_at=ASOF))
        d=self.calculate(r)['horses'][0]['role_indices']
        self.assertEqual(d['method'],'market_reference');self.assertIn('市場参考',d['label'])
        self.assertTrue(all(d[k]['value'] is None for k in ROLES));self.assertIsNotNone(d['market_reference']['value'])
    def test_today_or_future_result_rejected(self):
        r=race();r['horses'][0]['past']=[past(day='2026-11-01')]
        with self.assertRaises(ValueError):self.calculate(r)
    def test_history_obtained_later_than_cutoff_rejected(self):
        with self.assertRaises(ValueError):self.calculate(race(),history_by_number={1:dict(source=dict(retrieved_at='2026-11-01T09:00:00+09:00'))})
    def test_duplicate_run_is_not_double_counted(self):
        r=race();r['horses'][0]['past']*=2
        d=self.calculate(r)['horses'][0]['role_indices'];self.assertEqual(d['runs'],1)
    def test_debut_and_withdrawn_not_assigned_fake_zero(self):
        r=race();r['class_text']='新馬';d=self.calculate(r)['horses'][0]['role_indices'];self.assertEqual(d['method'],'not_computed');self.assertIsNone(d['first']['value'])
        r=race();r['horses'][0]['status_at_snapshot']='withdrawn';d=self.calculate(r)['horses'][0]['role_indices'];self.assertEqual(d['method'],'not_applicable')
    def test_post_event_computation_cannot_pass_pre_race_gate(self):
        out=apply_indices(race(),as_of=ASOF,computed_at='2026-11-01T11:00:00+09:00')
        self.assertIn('role_indices_definition_missing',[e[0] for e in audit_indices(out,ASOF)])

class CoveragePolicyTest(unittest.TestCase):
    def coverage(self):return dict(objective='capture_all_top3',not_guaranteed=True,reason='点数と印範囲を分離',candidate_groups={k:[1,2,3] for k in ROLES},scenario_groups=[dict(name=k,numbers=[1,2,3],reason='実走と別展開比較') for k in ['main','alternate']])
    def selected(self,**kwargs):
        r=race();return apply(r,[1,2,3],reviewed_at=ASOF,reason='3頭捕捉を優先',boundary_reviews=[dict(number=n,compared_with=[3],reason='直接比較',evidence_refs=['run-'+str(n),'run-3']) for n in [4,5]],coverage_review=self.coverage(),**kwargs)
    def test_future_policy_requires_coverage_and_minimum_three_marks(self):
        self.assertEqual(suggested_limit(6,COVERAGE_POLICY),3)
        with self.assertRaises(ValueError):apply(race(),[1,2,3],reviewed_at=ASOF,reason='比較',boundary_reviews=[])
        with self.assertRaises(ValueError):apply(race(),[1,2],reviewed_at=ASOF,reason='比較',boundary_reviews=[],coverage_review=self.coverage())
        self.assertEqual(audit_race(self.selected(),ASOF),[])
    def test_missing_alternate_scenario_cannot_pass(self):
        r=self.selected();r['analysis']['mark_selection']['coverage_review']['scenario_groups']=[]
        self.assertIn('top3_coverage_review_missing',[x[0] for x in audit_race(r,ASOF)])
    def test_role_candidate_omitted_from_marks_requires_direct_comparison(self):
        r=self.selected();r['analysis']['mark_selection']['coverage_review']['candidate_groups']['top3'].append(6)
        self.assertIn('mark_boundary_comparison_missing',[x[0] for x in audit_race(r,ASOF)])

if __name__=='__main__':unittest.main()
