import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from jra_order_objectives import evaluate, field_limits, order_errors, role_positions


class TestBuyOrder(unittest.TestCase):
    def test_fourth_pick_is_a_partner_at_every_field_size(self):
        for size in range(4,19):
            partner,cover=field_limits(size)
            self.assertEqual(partner,4)
            self.assertGreaterEqual(cover,partner)
        result={'rows':[{'number':n,'finish':f} for n,f in [(1,1),(4,2),(8,3)]],'payouts':[]}
        metrics=evaluate(list(range(1,9)),result,*field_limits(8))
        self.assertTrue(metrics['axis_and_partner'])
        self.assertFalse(metrics['joint'])

    def test_placing_all_and_ticket_hit_are_separate_with_tied_third(self):
        order=list(range(1,9))
        result={'rows':[{'number':n,'finish':f} for n,f in [(2,1),(1,2),(4,3),(8,3)]],
                'payouts':[{'kind':'quinella','numbers':[1,2]},
                           {'kind':'trio','numbers':[1,2,4]},{'kind':'trio','numbers':[1,2,8]}]}
        metrics=evaluate(order,result)
        self.assertTrue(metrics['trio'] and metrics['axis_top2'] and metrics['partner_2_4'])
        self.assertFalse(metrics['cover_7'] or metrics['joint'])

    def test_ties_and_missing_values(self):
        def horse(n,value,**detail):
            return dict(number=n,role_indices=dict(top2=dict(value=value),**detail))
        horses=[horse(1,54),horse(2,54),horse(3,53),horse(4,None),
                horse(5,55,method='debut_cohort_reference',matched_starters=0)]
        self.assertEqual(role_positions(horses,'top2'),{1:1,2:1,3:3,4:None,5:None})

    def test_detects_main_wide_without_first_pick(self):
        horses=[dict(number=i,rank=i,mark='◎' if i==1 else '○',
                     role_indices={},purchase_order=dict(rank=i,top2=None,top3=None)) for i in (1,2,3)]
        race=dict(horses=horses,analysis=dict(purchase_order=dict(first_seven=[1,2,3])),
                  bet_plans=[dict(selected_for_example=True,kind='wide',tickets=[dict(numbers=[1,2])])])
        self.assertEqual(order_errors(race),[])
        race['bet_plans'][0]['tickets'][0]['numbers']=[2,3]
        self.assertTrue(order_errors(race))

