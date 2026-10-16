"""Route all three venues using mocked menus and the historical Tokyo fixture."""
from pathlib import Path
from copy import deepcopy
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json,sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import watch_jra_results as w
from render_jra_prediction import legacy_result
FIX=Path(__file__).parent/'fixtures/jra'
class ThreeVenues(unittest.TestCase):
 def test_niigata_embedded_results_keep_official_code(self):
  d=dict(date_jst='2026-10-04',venue_key='niigata',forecast_ref=dict(version='v1',sha256='a'*64),updated_at='2026-10-04T17:00:00+09:00',last_poll_at=None,races=[])
  self.assertEqual(legacy_result(d)['baba_code'],4)
 def test_update_discovers_niigata_without_losing_other_venues(self):
  base=json.loads((FIX/'20261004-tokyo-r1.json').read_text(encoding='utf-8'));html=(FIX/'20261004-tokyo-r1.html').read_text(encoding='utf-8');venues=[('04','niigata','新潟'),('05','tokyo','東京'),('08','kyoto','京都')]
  menu_tokens={key:f'pw01srl01{code}2026040120261004/TEST' for code,key,label in venues}
  detail_tokens={key:f'pw01sde01{code}202604010120261004/TEST' for code,key,label in venues}
  link=lambda token:f'<a onclick="doAction(\'/JRADB/accessS.html\', \'{token}\')">fixture</a>'
  def fetch(endpoint,token,date,venue):
   source={'retrieved_at':'2026-10-04T18:49:00+09:00'}
   if token=='fixture-menu':return ''.join(link(t) for t in menu_tokens.values()),source
   key=next((key for key,t in menu_tokens.items() if t==token),None)
   if key:return link(detail_tokens[key]),source
   key=next(key for key,t in detail_tokens.items() if t==token);label=next(label for code,k,label in venues if key==k)
   return html.replace('東京',label),source
  races=[]
  for code,key,label in venues:
   race=deepcopy(base);race.update(venue_key=key,race_uid='fixture-'+key);races.append(race)
  forecast=dict(authority='jra',date_jst='2026-10-04',forecast_version='v1',venues=[dict(venue_key=key,label=label) for code,key,label in venues],races=races)
  with TemporaryDirectory(dir=Path(__file__).resolve().parent,prefix='jra-routing-') as td:
   root=Path(td);assert root.resolve().is_relative_to(Path(__file__).resolve().parent)
   (root/'forecast.json').write_text(json.dumps(forecast),encoding='utf-8')
   with patch.object(w,'ROOT',root),patch.object(w,'raw_fetch',side_effect=fetch),patch.object(w,'render_day_snapshot'):
    complete,changed=w.update(dict(forecast='forecast.json',date='2026-10-04',result_menu_cname='fixture-menu'))
   self.assertTrue(complete);self.assertEqual(len(changed),3)
   for code,key,label in venues:
    data=json.loads((root/f'data/results/jra/2026-10-04/v1/{key}.json').read_text(encoding='utf-8'))
    self.assertEqual(data['venue_key'],key);self.assertTrue(data['races'][0]['official_confirmed']);self.assertEqual(len(data['races'][0]['rows']),12)
if __name__=='__main__':unittest.main()
