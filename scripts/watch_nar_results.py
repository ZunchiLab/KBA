"""Keep today's official result feed fresh during one bounded Actions job."""
from datetime import datetime, timedelta
import json
import subprocess
import time

from update_nar_results import ROOT, JST, update


def git(*args, check=True):
    return subprocess.run(['git', *args], cwd=ROOT, check=check)


def publish(targets):
    html_paths = [str((ROOT/target['forecast']).with_suffix('.html').relative_to(ROOT)) for target in targets]
    git('add', '--', 'data/results/nar', 'data/results/sources', *html_paths)
    if git('diff', '--cached', '--quiet', check=False).returncode == 0:
        return
    git('commit', '-m', 'Update official NAR result snapshots')
    for attempt in range(3):
        git('pull', '--rebase', 'origin', 'main')
        if git('push', 'origin', 'HEAD:main', check=False).returncode == 0:
            return
        if attempt < 2:
            time.sleep(3)
    raise RuntimeError('Could not publish result snapshots after three attempts')


def main():
    # Stay below the hosted runner's six-hour limit, including final publication.
    deadline = datetime.now(JST) + timedelta(minutes=345)
    while True:
        git('pull', '--ff-only', 'origin', 'main')
        config = json.loads((ROOT/'data/results/targets.json').read_text(encoding='utf-8'))
        now = datetime.now(JST)
        until = datetime.fromisoformat(config['active_until'])
        targets = [target for target in config['targets'] if target['date'] == now.date().isoformat()]
        if not targets or now >= min(until, deadline) or not 9 <= now.hour < 23:
            print('Outside the requested meeting window; stopping.', flush=True)
            return
        if config.get('refresh_status') != 'continuous':
            print('Continuous updating has been disabled; stopping.', flush=True)
            return
        interval = max(1, int(config.get('refresh_interval_minutes', 2)))
        for target in targets:
            update(target, now, refresh_status='continuous', refresh_interval=interval)
        publish(targets)
        completed = all(json.loads((ROOT/'data/results/nar'/target['date']/(target['venue']+'.json')).read_text(encoding='utf-8')).get('complete') for target in targets)
        if completed:
            print('All requested races confirmed; stopping.', flush=True)
            return
        remaining = (min(until, deadline) - datetime.now(JST)).total_seconds()
        if remaining <= 0:
            return
        print(f'Published; checking again in {interval} minutes.', flush=True)
        time.sleep(min(interval * 60, remaining))


if __name__ == '__main__':
    main()
