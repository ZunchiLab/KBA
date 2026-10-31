import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from jra_rank_coverage import ordered_horses,needed_prefix

class CoverageTests(unittest.TestCase):
    def test_all_podium_horses_need_fifth_not_just_first_or_second(self):
        actual=[dict(number=8,finish=1),dict(number=3,finish=2),dict(number=6,finish=3)]
        self.assertEqual(needed_prefix([8,3,5,9,6],actual),5)
    def test_tied_third_kept_as_four_horses(self):
        actual=[dict(number=n,finish=f) for n,f in [(1,1),(2,2),(3,3),(4,3)]]
        self.assertEqual(needed_prefix([1,2,3,4],actual),4)
    def test_missing_identity_or_duplicate_order_stops_diagnostic(self):
        with self.assertRaises(ValueError):needed_prefix([1,2],[dict(number=3,finish=1)])
        with self.assertRaises(ValueError):needed_prefix([1,1],[dict(number=1,finish=1)])
    def test_role_ties_match_ui_old_rank_not_horse_number(self):
        hs=[dict(number=n,rank=r,role_indices=dict(top3=dict(value=v)),status_at_snapshot=s) for n,r,v,s in [(1,3,55,'declared'),(2,1,55,'declared'),(3,2,None,'declared'),(4,None,99,'withdrawn')]]
        order,available=ordered_horses(hs,'top3');self.assertEqual([h['number'] for h in order],[2,1,3]);self.assertEqual(available,2)
    def test_no_related_examples_is_not_a_predictive_order(self):
        hs=[dict(number=n,rank=n,role_indices=dict(method='debut_cohort_reference',matched_starters=0,top3=dict(value=50))) for n in [1,2,3]]
        self.assertEqual(ordered_horses(hs,'top3')[1],0)

if __name__=='__main__':unittest.main()
