import sys, unittest
from pathlib import Path
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch, Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import watch_jra_results as watch

CONFIG={'date':'2026-10-11','active_until':'2026-10-11T17:30:00+09:00','state_file':'.git/test-health.json','forecast':'unused.json'}

class JRAWorkerRecovery(unittest.TestCase):
    def args(self):
        return SimpleNamespace(config='data/results/jra-targets.json',state_file='.git/test-health.json',publish=True,recheck=False)
    def test_only_configured_day_and_deadline_are_active(self):
        for stamp,expected in [('2026-10-10T12:00:00+09:00',False),('2026-10-11T12:00:00+09:00',True),('2026-10-11T17:30:00+09:00',False),('2026-10-12T12:00:00+09:00',False)]:
            self.assertEqual(watch.meeting_active(CONFIG,datetime.fromisoformat(stamp)),expected)
        bad=dict(CONFIG,active_until='2026-10-12T17:30:00+09:00')
        with self.assertRaises(ValueError):watch.meeting_active(bad)
    def test_failed_child_restarts_and_completed_child_stops(self):
        with patch.object(watch,'load_config',return_value=CONFIG),patch.object(watch,'meeting_active',return_value=True),patch.object(watch,'saved_complete',return_value=True),patch.object(watch,'atomic') as health,patch.object(watch.time,'sleep') as sleep,patch.object(watch.subprocess,'run',side_effect=[SimpleNamespace(returncode=9),SimpleNamespace(returncode=0)]) as run:
            watch.supervise(self.args())
            self.assertEqual(run.call_count,2);sleep.assert_called_once()
            self.assertEqual(health.call_args[0][1]['state'],'restarting')
            self.assertIn('--worker',run.call_args[0][0]);self.assertIn('--state-file',run.call_args[0][0])
    def test_clean_but_incomplete_child_is_restarted(self):
        with patch.object(watch,'load_config',return_value=CONFIG),patch.object(watch,'meeting_active',return_value=True),patch.object(watch,'saved_complete',side_effect=[False,True]),patch.object(watch,'atomic'),patch.object(watch.time,'sleep'),patch.object(watch.subprocess,'run',return_value=SimpleNamespace(returncode=0)) as run:
            watch.supervise(self.args());self.assertEqual(run.call_count,2)
    def test_outside_window_does_not_spawn(self):
        with patch.object(watch,'load_config',return_value=CONFIG),patch.object(watch,'meeting_active',return_value=False),patch.object(watch.subprocess,'run') as run:
            watch.supervise(self.args());run.assert_not_called()
    def test_spawn_failure_is_recovered(self):
        with patch.object(watch,'load_config',return_value=CONFIG),patch.object(watch,'meeting_active',return_value=True),patch.object(watch,'saved_complete',return_value=True),patch.object(watch,'atomic'),patch.object(watch.time,'sleep'),patch.object(watch.subprocess,'run',side_effect=[OSError('transient start failure'),SimpleNamespace(returncode=0)]) as run:
            watch.supervise(self.args());self.assertEqual(run.call_count,2)
    def test_cloud_health_override_avoids_windows_path(self):
        self.assertEqual(watch.state_path(self.args(),CONFIG),watch.ROOT/'.git/test-health.json')

if __name__=='__main__':unittest.main()
