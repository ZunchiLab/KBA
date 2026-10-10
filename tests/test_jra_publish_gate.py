"""Exercise the real publisher's rejection before any Git/network/publication action."""
from pathlib import Path
from tempfile import TemporaryDirectory
import json,subprocess,unittest
from test_jra_forecast_gate import fixture
ROOT=Path(__file__).resolve().parents[1]

class PublisherGate(unittest.TestCase):
    def test_next_day_incomplete_review_is_not_published(self):
        with TemporaryDirectory(prefix='jra-gate-',dir=ROOT.parent) as tmp:
            folder=Path(tmp);p=fixture();p.update(date_jst='2026-10-11',forecast_version='v1',model_version='TEST-FIXTURE-NOT-FORECAST')
            del p['races'][0]['analysis']['preflight_review']['single_win_edge']
            jp=folder/'gate-fixture.json';hp=folder/'gate-fixture.html'
            jp.write_text(json.dumps(p,ensure_ascii=False),encoding='utf-8');hp.write_text('<a href="gate-fixture.json">fixture</a>',encoding='utf-8')
            name='report_20261011_jra_predictions_v999.html'
            self.assertFalse((ROOT/'predictions'/name).exists())
            result=subprocess.run(['pwsh','-NoProfile','-File',str(ROOT/'scripts/publish_prediction.ps1'),'-HtmlPath',str(hp),'-JsonPath',str(jp),'-PublishedHtmlName',name,'-PrepareOnly'],cwd=ROOT,text=True,encoding='utf-8',capture_output=True,timeout=20)
            self.assertNotEqual(result.returncode,0);self.assertIn('single_win_edge_missing',result.stdout);self.assertIn('JRAの公開前比較',result.stderr)
            self.assertFalse((ROOT/'predictions'/name).exists());self.assertFalse((ROOT/'predictions'/name.replace('.html','.json')).exists())
if __name__=='__main__':unittest.main()
