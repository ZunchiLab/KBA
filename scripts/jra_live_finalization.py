"""Lock the displayed order and ticket set before JRA internet sales close."""
from datetime import datetime, timedelta

POLICY = 'ipat-close-minus-five-v1'
SALES_CLOSE = 'https://www.jra.go.jp/dento/soku/instructions/hatsubai/jra.html'


def deadline(race):
    # Ordinary same-day IPAT sales close one minute before scheduled post.
    # The three-minute delivery window allows for polling and publication.
    return datetime.fromisoformat(race['start_at']) - timedelta(minutes=6)


def final_window(race):
    return deadline(race) - timedelta(minutes=3)


def morning_revision(race):
    horses = sorted((h for h in race['horses'] if h.get('rank')),key=lambda h:h['rank'])
    mode = '市場参考' if race['class_text']=='新馬' else '比較保留' if race['surface']=='hurdle' else '朝版'
    fixed = race['fixed_at']
    return dict(version=POLICY,calculated_at=fixed,source_checked_at=race.get('source_checked_at'),
                mode=mode,order=[h['number'] for h in horses],
                marks={str(h['number']):h['mark'] for h in horses},
                withdrawn=[],changes=[],horse_evidence=[],same_surface_results=[],trend_used=False,
                market_comparable=False,main_review=dict(decision='見送り',kind=None,tickets=[],
                    reason='締切前の再評価を取得できず、朝の印を最終保存。価格条件不明のため購入案は見送り。'))


def finalize(item, race, now):
    """Create exactly one final record using only information available by the cutoff."""
    if item.get('final'):
        return item['final']
    cutoff = deadline(race)
    if now < final_window(race):
        return None
    valid = [s['revision'] for s in item['snapshots'] if s.get('revision')
             and datetime.fromisoformat(s['revision']['calculated_at']) <= min(now,cutoff)]
    revision = max(valid,key=lambda r:datetime.fromisoformat(r['calculated_at'])) if valid else morning_revision(race)
    final = dict(policy=POLICY,cutoff_at=cutoff.isoformat(timespec='seconds'),
                 fixed_at=now.isoformat(timespec='seconds'),late=now>cutoff,
                 basis='live' if valid else 'morning',revision=revision,
                 source=SALES_CLOSE)
    item['final'] = final
    return final
