import copy, sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from jra_mark_policy import apply, audit_race, suggested_limit

def sample():
    return dict(start_at='2026-10-31T10:00:00+09:00',surface='芝',horses=[dict(number=n,rank=n,score=90-n,score_method='independent',mark='◎' if n==1 else '注',status_at_snapshot='declared',evidence_refs=[f'run-{n}']) for n in range(1,10)],bet_plans=[dict(selected_for_example=True,tickets=[dict(numbers=[1,2])])],analysis={})

class MarkPolicyTest(unittest.TestCase):
    def marked(self):
        return apply(sample(),[1,2,3],reviewed_at='2026-10-31T09:00:00+09:00',reason='同条件と別展開で3頭を比較。',boundary_reviews=[dict(number=n,compared_with=[3],reason='同じ相手枠を比較。',evidence_refs=[f'run-{n}','run-3']) for n in [4,5]])

    def test_field_size_bands(self):
        self.assertEqual([suggested_limit(n) for n in [0,1,6,7,9,10,12,13,15,16,18]],[0,1,2,3,3,4,4,5,5,6,6])

    def test_does_not_mutate_source_or_scores_or_bets(self):
        source=sample();before=copy.deepcopy(source)
        result=apply(source,[1,2,3],reviewed_at='2026-10-31T09:00:00+09:00',reason='3頭を比較。',boundary_reviews=[dict(number=n,compared_with=[3],reason='相手枠を比較。',evidence_refs=[f'run-{n}','run-3']) for n in [4,5]])
        self.assertEqual(source,before)
        self.assertEqual(result['bet_plans'],source['bet_plans'])
        self.assertEqual([(h['score'],h['rank']) for h in result['horses']],[(h['score'],h['rank']) for h in source['horses']])
        self.assertEqual([h['number'] for h in result['horses'] if h['mark']!='無印'],[1,2,3])
        self.assertEqual(audit_race(result,'2026-10-31T09:10:00+09:00'),[])

    def test_no_quota_filling(self):
        r=sample();r['bet_plans']=[]
        a=apply(r,[],reviewed_at='2026-10-31T09:00:00+09:00',reason='独自比較不足で印保留。',boundary_reviews=[])
        self.assertFalse(audit_race(a,'2026-10-31T09:10:00+09:00'))
        self.assertTrue(all(h['mark']=='無印' for h in a['horses']))

    def test_missing_record_fails(self):
        self.assertEqual(audit_race(sample(),'2026-10-31T09:10:00+09:00')[0][0],'mark_selection_missing')

    def test_unsupported_main_cannot_be_hidden(self):
        with self.assertRaises(ValueError):
            apply(sample(),[1,3],reviewed_at='2026-10-31T09:00:00+09:00',reason='比較',boundary_reviews=[])

    def test_exception_must_be_visible(self):
        with self.assertRaises(ValueError):
            apply(sample(),[1,2,3,4],reviewed_at='2026-10-31T09:00:00+09:00',reason='比較',boundary_reviews=[])
        a=self.marked();a['analysis']['mark_selection']['marked_numbers'].append(4);a['horses'][3]['mark']='△'
        self.assertIn('mark_limit_exception_missing',[e[0] for e in audit_race(a,'2026-10-31T09:10:00+09:00')])

    def test_no_marking_withdrawn_runner(self):
        a=self.marked();a['horses'][3]['status_at_snapshot']='withdrawn'
        a['analysis']['mark_selection']['field_size_at_review']=8
        self.assertIn('mark_boundary_comparison_missing',[e[0] for e in audit_race(a,'2026-10-31T09:10:00+09:00')])
        a['analysis']['mark_selection']['boundary_reviews'].append(dict(number=6,compared_with=[3],reason='取消後の境界を再比較。',evidence_refs=['run-6','run-3']))
        self.assertFalse(audit_race(a,'2026-10-31T09:10:00+09:00'))
        with self.assertRaises(ValueError):
            apply(a,[1,2,4],reviewed_at='2026-10-31T09:00:00+09:00',reason='比較',boundary_reviews=[])

    def test_boundary_and_prospective_time_fail_closed(self):
        a=self.marked();a['analysis']['mark_selection']['boundary_reviews']=[]
        self.assertIn('mark_boundary_comparison_missing',[e[0] for e in audit_race(a,'2026-10-31T09:10:00+09:00')])
        a=self.marked();a['analysis']['mark_selection']['reviewed_at']='2026-10-31T10:01:00+09:00'
        self.assertIn('mark_selection_time_or_reason_missing',[e[0] for e in audit_race(a,'2026-10-31T09:10:00+09:00')])

if __name__=='__main__':unittest.main()
