"""Official 2026-10-04 Tokyo 1R extracted fixture; no current-day result used."""
import sys,json,unittest
from pathlib import Path
from copy import deepcopy
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from watch_jra_results import parse
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
        for field,value in [('start_at','2026-10-03T10:05:00+09:00'),('venue_key','kyoto'),('race_no',2),('name','他のレース')]:
            with self.subTest(field=field):
                f=deepcopy(self.f);f[field]=value
                with self.assertRaises(ValueError):parse(self.html,f,self.source)
    def test_wrong_horse_identity_rejected(self):
        f=deepcopy(self.f);f['horses'][0]['name']='他の馬'
        with self.assertRaises(ValueError):parse(self.html,f,self.source)
    def test_incomplete_payouts_not_confirmed(self):
        html=self.html.replace('class="wide"','class="unknown"')
        r=parse(html,self.f,self.source)
        self.assertFalse(r['official_confirmed']);self.assertEqual(r['status'],'partial')
if __name__=='__main__':unittest.main()
