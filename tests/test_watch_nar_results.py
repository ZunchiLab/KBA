"""Regression checks for the 2026-10-09 failed GitHub pull incident."""
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch, Mock
import json
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import watch_nar_results as w


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.addCleanup(patch.stopall)
        patch.object(w, 'ROOT', self.root).start()
        self.now = datetime.now(w.JST)
        self.targets = [dict(date=self.now.date().isoformat(), venue=v, forecast='predictions/day.json') for v in ('sonoda', 'ooi')]
        self.config = dict(active_until=(self.now+timedelta(minutes=30)).isoformat(), targets=self.targets,
                           execution_environment='local', refresh_status='continuous', refresh_interval_minutes=2)
        forecast = self.root/'predictions/day.json'
        forecast.parent.mkdir()
        forecast.write_text(json.dumps(dict(races=[dict(venue_key=v, start_at=(self.now-timedelta(minutes=10)).isoformat()) for v in ('sonoda', 'ooi')])) ,encoding='utf-8')
        forecast.with_suffix('.html').write_text('results', encoding='utf-8')
        for target in self.targets:
            p = w.result_path(target)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('{"complete": true}', encoding='utf-8')
        self.git = patch.object(w, 'git', return_value=subprocess.CompletedProcess([], 0, stdout='')).start()
        self.sleep = patch.object(w.time, 'sleep').start()
        def bounded_sleep(_):
            if self.sleep.call_count > 12:
                raise KeyboardInterrupt('Test retry budget exhausted')
        self.sleep.side_effect = bounded_sleep

    def failed(self):
        return subprocess.CalledProcessError(128, ['git', 'pull'], stderr='Empty reply from server')

    def test_pull_failure_retried(self):
        failed = False
        def git(*args, **kwargs):
            nonlocal failed
            if args[:2] == ('pull', '--rebase') and not failed:
                failed = True
                raise self.failed()
            return subprocess.CompletedProcess([], 0, stdout='')
        self.git.side_effect = git
        w.publish(self.targets)
        self.assertEqual(sum(c.args[:2] == ('pull', '--rebase') for c in self.git.call_args_list), 2)

    def test_no_diff_still_pushes_queued_commits(self):
        w.publish(self.targets)
        self.git.assert_any_call('push', 'origin', 'HEAD:main')
        self.assertFalse(any(c.args[0] == 'commit' for c in self.git.call_args_list))

    def test_three_failed_pushes_leave_queue_for_next_cycle(self):
        self.git.side_effect = lambda *a, **k: (_ for _ in ()).throw(self.failed()) if a[0] == 'push' else subprocess.CompletedProcess([], 0, stdout='')
        with self.assertRaisesRegex(RuntimeError, 'queued commits retained'):
            w.publish(self.targets)
        self.assertEqual(sum(c.args[0] == 'push' for c in self.git.call_args_list), 3)

    def test_timeout_is_retried(self):
        count = 0
        def git(*a, **k):
            nonlocal count
            if a[0] == 'push':
                count += 1
                if count == 1:
                    raise subprocess.TimeoutExpired('git push', 45)
            return subprocess.CompletedProcess([], 0, stdout='')
        self.git.side_effect = git
        w.publish(self.targets)
        self.assertEqual(count, 2)

    def test_unrelated_staged_files_are_not_committed(self):
        def git(*a, **k):
            return subprocess.CompletedProcess([], 0, stdout='docs/other-work.md\n' if a[:3] == ('diff', '--cached', '--name-only') else '')
        self.git.side_effect = git
        with self.assertRaisesRegex(RuntimeError, 'Unrelated staged'):
            w.publish(self.targets)
        self.assertFalse(any(c.args[0] in ('add', 'commit', 'push') for c in self.git.call_args_list))

    def test_staging_scoped_to_target_dates_and_venues(self):
        w.publish(self.targets)
        added = next(c.args[2:] for c in self.git.call_args_list if c.args[0] == 'add')
        self.assertNotIn('data/results/nar', added)
        self.assertNotIn('data/results/sources', added)
        self.assertIn('predictions/day.html', added)

    def test_complete_waits_for_successful_publication(self):
        with patch.object(w, 'load_config', return_value=self.config), patch.object(w, 'update') as update, patch.object(w, 'publish', side_effect=[self.failed(), None]) as publish:
            w.run_worker(True, self.root/'health.json')
        self.assertEqual(publish.call_count, 2)
        self.assertEqual(update.call_count, 4)
        self.assertEqual(json.loads((self.root/'health.json').read_text())['state'], 'complete')

    def test_sync_failure_still_collects_both_venues(self):
        self.git.side_effect = lambda *a, **k: (_ for _ in ()).throw(self.failed()) if a[:2] == ('pull', '--ff-only') else subprocess.CompletedProcess([], 0, stdout='')
        with patch.object(w, 'load_config', return_value=self.config), patch.object(w, 'update') as update, patch.object(w, 'publish'):
            w.run_worker(True)
        self.assertEqual(update.call_count, 2)

    def test_one_venue_failure_does_not_block_other_venue(self):
        with patch.object(w, 'load_config', return_value=self.config), patch.object(w, 'update', side_effect=[ValueError('bad identity'), None, None, None]) as update, patch.object(w, 'publish'):
            w.run_worker(True)
        self.assertEqual(update.call_count, 4)
        self.assertEqual(update.call_args_list[1].args[0]['venue'], 'ooi')

    def test_future_day_and_disabled_environment_do_not_poll(self):
        for change in (dict(targets=[dict(self.targets[0], date='2099-01-01')]), dict(execution_environment='github'), dict(refresh_status='disabled'), dict(active_until=(self.now-timedelta(seconds=1)).isoformat())):
            with self.subTest(change=change), patch.object(w, 'load_config', return_value=dict(self.config, **change)), patch.object(w, 'update') as update, patch.object(w, 'publish') as publish:
                w.run_worker(True)
                update.assert_not_called()
                publish.assert_not_called()

    def test_supervisor_restarts_failed_child(self):
        with patch.object(w, 'load_config', return_value=self.config), patch.object(w.subprocess, 'run', side_effect=[subprocess.CompletedProcess([], 1), subprocess.CompletedProcess([], 0)]) as run:
            w.supervise()
        self.assertEqual(run.call_count, 2)
        self.assertIn('--worker', run.call_args.args[0])

    def test_supervisor_does_not_restart_normal_completion(self):
        with patch.object(w, 'load_config', return_value=self.config), patch.object(w.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as run:
            w.supervise()
        self.assertEqual(run.call_count, 1)

    def test_duplicate_worker_rejected_and_lock_released(self):
        with w.single_instance():
            with self.assertRaises(OSError):
                with w.single_instance():
                    self.fail('Duplicate worker acquired the same lock')
        with w.single_instance():
            pass

    def test_existing_rebase_is_held(self):
        (self.root/'rebase-merge').mkdir()
        self.git.side_effect = lambda *a, **k: subprocess.CompletedProcess([], 0, stdout=a[-1] if a[:2] == ('rev-parse', '--git-path') else '')
        with self.assertRaisesRegex(RuntimeError, 'Existing merge/rebase'):
            w.publish(self.targets)
        self.assertFalse(any(c.args[0] == 'push' for c in self.git.call_args_list))

    def test_unwritable_health_does_not_stop_results(self):
        with patch.object(w, 'write_atomic', side_effect=PermissionError('health denied')), patch.object(w, 'load_config', return_value=self.config), patch.object(w, 'update') as update, patch.object(w, 'publish'):
            w.run_worker(True, self.root/'health.json')
        self.assertEqual(update.call_count, 2)

    def test_prestart_wait_does_not_publish_empty_updates(self):
        path = self.root/'predictions/day.json'
        data = json.loads(path.read_text())
        for race in data['races']:
            race['start_at'] = (self.now+timedelta(minutes=10)).isoformat()
        path.write_text(json.dumps(data), encoding='utf-8')
        expired = dict(self.config, active_until=(self.now-timedelta(seconds=1)).isoformat())
        with patch.object(w, 'load_config', side_effect=[self.config, self.config, expired]), patch.object(w, 'update') as update, patch.object(w, 'publish') as publish:
            w.run_worker(True)
        update.assert_not_called()
        publish.assert_not_called()


class LocalGitIntegration(unittest.TestCase):
    def test_real_git_resends_already_committed_data_after_connection_failure(self):
        with TemporaryDirectory() as tmp:
            root, remote = Path(tmp)/'checkout', Path(tmp)/'remote.git'
            subprocess.run(['git', 'init', '--bare', str(remote)], check=True, capture_output=True)
            subprocess.run(['git', 'init', '-b', 'main', str(root)], check=True, capture_output=True)
            def local_git(*args):
                return subprocess.run(['git', *args], cwd=root, check=True, capture_output=True, text=True)
            local_git('config', 'user.name', 'KBA test')
            local_git('config', 'user.email', 'kba-test@example.invalid')
            (root/'predictions').mkdir()
            (root/'predictions/day.html').write_text('fixed prediction', encoding='utf-8')
            local_git('add', '.')
            local_git('commit', '-m', 'Initial fixture')
            local_git('remote', 'add', 'origin', str(remote))
            local_git('push', 'origin', 'HEAD:main')
            (root/'predictions/day.html').write_text('fixed prediction plus result', encoding='utf-8')
            local_git('add', '.')
            local_git('commit', '-m', 'Queued snapshot after failed push')
            original_git = w.git
            failed = False
            def intermittent(*a, **k):
                nonlocal failed
                if a[:2] == ('pull', '--rebase') and not failed:
                    failed = True
                    raise subprocess.CalledProcessError(128, ['git', 'pull'], stderr='Empty reply from server')
                return original_git(*a, **k)
            target = dict(date='2026-10-09', venue='sonoda', forecast='predictions/day.json')
            with patch.object(w, 'ROOT', root), patch.object(w, 'git', side_effect=intermittent), patch.object(w.time, 'sleep'):
                w.publish([target])
            head = local_git('rev-parse', 'HEAD').stdout.strip()
            self.assertEqual(local_git('ls-remote', 'origin', 'refs/heads/main').stdout.split()[0], head)
            self.assertEqual(local_git('status', '--porcelain').stdout, '')


if __name__ == '__main__':
    unittest.main()
