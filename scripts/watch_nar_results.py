"""Bounded NAR collector: retry failed cycles, resend commits, supervise locally."""
from argparse import ArgumentParser, SUPPRESS
from contextlib import contextmanager
from datetime import datetime, timedelta
from hashlib import sha256
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import time
from update_nar_results import ROOT, JST, update, write_atomic

GIT_TIMEOUT = 45


def git(*args, check=True, capture=False):
    return subprocess.run(['git', *args], cwd=ROOT, check=check, timeout=GIT_TIMEOUT,
                          text=True, capture_output=capture)


def result_path(target):
    return ROOT/'data/results/nar'/target['date']/target.get('result_version', '')/(target['venue']+'.json')


def publication_paths(targets):
    paths = set()
    for target in targets:
        paths.add(result_path(target).relative_to(ROOT).as_posix())
        paths.add('data/results/sources/'+target['date']+'/'+target['venue'])
        paths.add((ROOT/target['forecast']).with_suffix('.html').relative_to(ROOT).as_posix())
    return sorted(paths)


def ensure_repository_ready():
    for name in ('rebase-merge', 'rebase-apply', 'MERGE_HEAD'):
        value = git('rev-parse', '--git-path', name, capture=True).stdout.strip()
        if value and (ROOT/value).exists():
            raise RuntimeError('Existing merge/rebase in progress; collection/publication held')


def publish(targets):
    ensure_repository_ready()
    paths = publication_paths(targets)
    staged = git('diff', '--cached', '--name-only', capture=True).stdout.splitlines()
    if any(not any(p == a or p.startswith(a+'/') for a in paths) for p in staged):
        raise RuntimeError('Unrelated staged changes; result publication held')
    existing = [p for p in paths if (ROOT/p).exists()]
    if existing:
        git('add', '--', *existing)
    difference = git('diff', '--cached', '--quiet', check=False).returncode
    if difference not in (0, 1):
        raise RuntimeError('Could not inspect staged result changes')
    if difference == 1:
        git('commit', '-m', 'Update official NAR result snapshots')
    # No new diff does not imply no queued commit: retry previously failed pushes.
    for attempt in range(3):
        try:
            git('pull', '--rebase', 'origin', 'main')
            git('push', 'origin', 'HEAD:main')
            return
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as error:
            # Only undo a rebase initiated above; never continue on an intermediate tree.
            try:
                for name in ('rebase-merge', 'rebase-apply'):
                    value = git('rev-parse', '--git-path', name, capture=True).stdout.strip()
                    if value and (ROOT/value).exists():
                        git('rebase', '--abort', check=False)
                        break
            except (subprocess.SubprocessError, OSError):
                pass
            print(f'Publication attempt {attempt+1}/3 failed: {error}', flush=True)
            if attempt < 2:
                time.sleep((3, 10)[attempt])
    raise RuntimeError('Publication unavailable; queued commits retained for next cycle')


def health(path, state, **fields):
    if path:
        try:
            write_atomic(Path(path), dict(state=state, at=datetime.now(JST).isoformat(timespec='seconds'),
                                         pid=os.getpid(), **fields))
        except OSError as error:
            print(f'Health record unavailable; collection continues: {error}', flush=True)


def load_config():
    return json.loads((ROOT/'data/results/targets.json').read_text(encoding='utf-8'))


def meeting(config, local, deadline):
    now = datetime.now(JST)
    until = min(datetime.fromisoformat(config['active_until']), deadline)
    targets = [t for t in config['targets'] if t['date'] == now.date().isoformat()]
    allowed = (config.get('execution_environment', 'github') == ('local' if local else 'github')
               and config.get('refresh_status') == 'continuous' and bool(targets)
               and now < until and 9 <= now.hour < 23)
    return now, until, targets, allowed


def run_worker(local=False, state_file=None):
    deadline = datetime.now(JST)+(timedelta(hours=12) if local else timedelta(minutes=345))
    failures, last_publish = 0, None
    while True:
        try:
            config = load_config()
            now, until, targets, allowed = meeting(config, local, deadline)
            if not allowed:
                health(state_file, 'stopped', reason='Outside configured meeting or updating disabled',
                       last_publish_at=last_publish)
                print('Outside the configured meeting window; stopping.', flush=True)
                return
            interval = max(1, int(config.get('refresh_interval_minutes', 2)))
            ensure_repository_ready()
            try:
                git('pull', '--ff-only', 'origin', 'main')
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as error:
                print(f'Main sync failed; continuing local collection: {error}', flush=True)
            config = load_config()  # A pull may change targets or disable the worker.
            now, until, targets, allowed = meeting(config, local, deadline)
            if not allowed:
                continue
            starts = [datetime.fromisoformat(r['start_at']) for target in targets
                      for r in json.loads((ROOT/target['forecast']).read_text(encoding='utf-8-sig'))['races']
                      if r.get('venue_key', target['venue']) == target['venue']]
            if starts and min(starts) > now:
                delay = min(interval*60, max(1, (min(until, min(starts))-now).total_seconds()))
                health(state_file, 'waiting_for_start', next_start_at=min(starts).isoformat())
                print(f'Waiting for first start {min(starts).isoformat()}.', flush=True)
                time.sleep(delay)
                continue
            health(state_file, 'collecting', consecutive_failures=failures, last_publish_at=last_publish)
            errors = []
            for target in targets:
                try:
                    update(target, now, refresh_status='continuous', refresh_interval=interval)
                except Exception as error:
                    errors.append(f'{target["venue"]}: {error}')
                    print(f'Target failed; other venues continue: {errors[-1]}', flush=True)
            publish(targets)
            last_publish = datetime.now(JST).isoformat(timespec='seconds')
            complete = not errors and all(json.loads(result_path(t).read_text(encoding='utf-8')).get('complete') for t in targets)
            failures = 0
            health(state_file, 'complete' if complete else 'published', last_publish_at=last_publish,
                   collection_errors=errors, consecutive_failures=0)
            if complete:
                print('All requested races confirmed and published; stopping.', flush=True)
                return
            remaining = (until-datetime.now(JST)).total_seconds()
            if remaining <= 0:
                print('Meeting window ended; unconfirmed races remain in saved snapshots.', flush=True)
                return
            print(f'Published; checking again in {interval} minutes.', flush=True)
            time.sleep(min(interval*60, remaining))
        except Exception as error:
            failures += 1
            remaining = (deadline-datetime.now(JST)).total_seconds()
            try:
                remaining = min(remaining, (datetime.fromisoformat(load_config()['active_until'])-datetime.now(JST)).total_seconds())
            except Exception:
                pass
            delay = min(60, 5*(2**min(failures-1, 4)), max(0, remaining))
            print(f'Recoverable cycle failure {failures}: {error}; retry in {delay:g}s. Local data/commits retained.', flush=True)
            try:
                health(state_file, 'retrying', error=str(error), consecutive_failures=failures,
                       next_retry_seconds=delay, last_publish_at=last_publish)
            except OSError as state_error:
                print(f'Could not write health record: {state_error}', flush=True)
            if delay <= 0:
                raise
            time.sleep(delay)


@contextmanager
def single_instance():
    key = sha256(str(ROOT.resolve()).encode()).hexdigest()[:20]
    with (Path(tempfile.gettempdir())/('kba-nar-worker-'+key+'.lock')).open('a+b') as handle:
        handle.seek(0)
        if not handle.read(1):
            handle.write(b'0')
            handle.flush()
        handle.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == 'nt':
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def supervise(state_file=None):
    """Restart an unexpectedly failed local child within today's configured window."""
    deadline = datetime.now(JST)+timedelta(hours=12)
    while True:
        try:
            now, until, _, allowed = meeting(load_config(), True, deadline)
        except Exception as error:
            if datetime.now(JST) >= deadline:
                raise
            print(f'Local supervisor configuration error: {error}; retrying.', flush=True)
            time.sleep(15)
            continue
        if not allowed:
            return
        command = [sys.executable, '-u', '-X', 'utf8', str(Path(__file__).resolve()), '--local', '--worker']
        if state_file:
            command += ['--state-file', str(state_file)]
        try:
            child = subprocess.run(command, cwd=ROOT, timeout=max(1, (until-now).total_seconds())+120)
            if child.returncode == 0:
                return
            reason = f'Worker exited with code {child.returncode}'
        except (subprocess.TimeoutExpired, OSError) as error:
            reason = str(error)
        print(f'Local supervisor: {reason}; restarting within meeting window.', flush=True)
        health(state_file, 'restarting', reason=reason)
        time.sleep(min(15, max(0, (until-datetime.now(JST)).total_seconds())))


def main():
    parser = ArgumentParser()
    parser.add_argument('--local', action='store_true')
    parser.add_argument('--worker', action='store_true', help=SUPPRESS)
    parser.add_argument('--state-file', help='Local health record (not committed)')
    args = parser.parse_args()
    if args.worker:
        run_worker(args.local, args.state_file)
    else:
        with single_instance():
            if args.local:
                supervise(args.state_file)
            else:
                run_worker(False, args.state_file)


if __name__ == '__main__':
    main()
