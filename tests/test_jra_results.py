"""Official 2026-10-04 Tokyo 1R extracted fixture; no current-day result used."""
import sys,json,unittest
from pathlib import Path
from copy import deepcopy
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from watch_jra_results import parse
from bs4 import BeautifulSoup
from jra_payouts import PAYOUT_KINDS,payout_html
FIX=Path(__file__).parent/'fixtures/jra'

class JRAResults(unittest.TestCase):
    def setUp(self):
        self.html=(FIX/'20261004-tokyo-r1.html').read_text(encoding='utf-8')
        self.f=json.loads((FIX/'20261004-tokyo-r1.json').read_text(encoding='utf-8'))
        self.f['venue_key']='tokyo'
        self.source={'retrieved_at':'2026-10-04T18:49:00+09:00'}
    def test_all_runners_and_payouts(self):
        r=parse(self.html,self.f,self.source)
        self.assertTrue(r['official_confirmed']);self.assertEqual(len(r['rows']),12)
        self.assertEqual(len(r['payouts']),12)
        self.assertEqual(sum(p['kind']=='wide' for p in r['payouts']),3)
        self.assertEqual(sum(p['kind']=='place' for p in r['payouts']),3)
    def test_foreign_date_venue_number_title_rejected(self):
        for field,value in [('start_at','2026-10-03T10:05:00+09:00'),('venue_key','kyoto'),('venue_key','niigata'),('race_no',2),('name','他のレース')]:
            with self.subTest(field=field):
                f=deepcopy(self.f);f[field]=value
                with self.assertRaises(ValueError):parse(self.html,f,self.source)
    def test_wrong_horse_identity_rejected(self):
        f=deepcopy(self.f);f['horses'][0]['name']='他の馬'
        with self.assertRaises(ValueError):parse(self.html,f,self.source)
    def test_average_one_furlong_is_not_final_three_furlongs(self):
        soup=BeautifulSoup(self.html,'html.parser');soup.select_one('th.f_time').string='平均1F'
        r=parse(str(soup),self.f,self.source)
        self.assertTrue(all(h['last_3f'] is None and 'average_1f' in h for h in r['rows']))
        original=parse(self.html,self.f,self.source)
        self.assertEqual(r['payouts'],original['payouts'])
        self.assertEqual([h['average_1f'] for h in r['rows']],[h['last_3f'] for h in original['rows']])
    def test_incomplete_payouts_not_confirmed(self):
        html=self.html.replace('class="wide"','class="unknown"')
        r=parse(html,self.f,self.source)
        self.assertFalse(r['official_confirmed']);self.assertEqual(r['status'],'partial')
    def test_exacta_and_bracket_payouts_are_required_for_large_fields(self):
        for css in ['umatan','wakuren']:
            with self.subTest(css=css):
                r=parse(self.html.replace('class="'+css+'"','class="unknown"'),self.f,self.source)
                self.assertFalse(r['official_confirmed'])
                self.assertEqual(r['payouts_status']['exacta' if css=='umatan' else 'bracket_quinella'],'pending')
    def test_all_eight_statuses_and_ordered_numbers(self):
        r=parse(self.html,self.f,self.source)
        self.assertEqual(set(r['payouts_status']),set(PAYOUT_KINDS))
        self.assertTrue(all(v=='confirmed' for v in r['payouts_status'].values()))
        soup=BeautifulSoup(self.html,'html.parser')
        for css,kind in [('umatan','exacta'),('tierce','trifecta')]:
            number=soup.select_one('li.'+css+' .num').get_text(strip=True)
            import re
            expected=[int(n) for n in re.findall(r'\d+',number)]
            self.assertEqual(next(p['numbers'] for p in r['payouts'] if p['kind']==kind),expected)
    def test_blank_does_not_become_zero_or_not_offered(self):
        soup=BeautifulSoup(self.html,'html.parser');soup.select_one('li.wakuren .line').clear()
        r=parse(str(soup),self.f,self.source)
        self.assertEqual(r['payouts_status']['bracket_quinella'],'pending')
        self.assertFalse(any(p['kind']=='bracket_quinella' for p in r['payouts']))
        soup.select_one('li.wakuren .line').string='発売なし'
        r=parse(str(soup),self.f,self.source)
        self.assertEqual(r['payouts_status']['bracket_quinella'],'not_offered')
    def test_static_payout_table_works_without_javascript(self):
        r=dict(rows=[dict(number=11,finish=1),dict(number=3,finish=2),dict(number=10,finish=2)],refunds=[dict(kind='馬単',numbers=[11,3],yen_per_100=4180),dict(kind='三連単',numbers=[11,3,10],yen_per_100=17820),dict(kind='複勝',numbers=[11],yen_per_100=220),dict(kind='複勝',numbers=[3],yen_per_100=120)],payouts_status={'bracket_quinella':'not_offered'},source=self.source)
        soup=BeautifulSoup(payout_html(r),'html.parser')
        self.assertEqual(len(soup.select('tbody tr')),8)
        self.assertTrue(soup.details.has_attr('open'))
        self.assertEqual(soup.select_one('tr[data-kind="exacta"] .payout-line').get_text(' ',strip=True),'11→3 4,180円')
        self.assertIn('11→3→10',soup.get_text())
        self.assertIn('枠連（枠番）',soup.get_text());self.assertIn('発売なし',soup.get_text())
        self.assertIn('2着 3・10',soup.get_text());self.assertEqual(len(soup.select('tr[data-kind="place"] .payout-line')),2)
        self.assertIn('未掲載・確認待ち',soup.get_text())
        self.assertEqual(payout_html(dict(rows=[],refunds=[])),'')
if __name__=='__main__':unittest.main()
