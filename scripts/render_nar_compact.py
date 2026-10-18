"""NAR data adapter for the same compact renderer and CSS used by JRA."""
from copy import deepcopy
from nar_display import ordinal_score, adapt_result

def render(data, json_name, results=None):
    from render_jra_compact import render as render_compact
    d = deepcopy(data)
    d['authority'] = 'nar'
    d.setdefault('presentation', {}).update(layout='compact-v1', detailed_rank_labels=True,
                                          price_eligible_defaults=True)
    for race in d['races']:
        race.setdefault('grade', '')
        for plan in race['bet_plans']:
            plan['all_points_price_condition_at_snapshot'] = all(
                t.get('price_condition_at_snapshot') is True for t in plan['tickets'])
        for horse in race['horses']:
            original = horse.get('score')
            if ordinal_score(horse) or original is None:
                horse['score'] = None
                horse['score_method'] = 'not_computed'
                horse['model_rank'] = None
                horse['mark_override_reason'] = ('能力指数は未算出。総合印は人手の比較順位。'
                    + (f'旧原本の{original}は順位表示用数値で、能力差ではありません。'
                       if original is not None and ordinal_score(horse) else '根拠・懸念・採否を確認してください。'))
            else:
                horse.setdefault('score_method', 'unverified')
            horse.setdefault('style', '位置取りは詳細')
            horse.setdefault('weight', horse.get('market', {}).get('weight', '未確認'))
            horse.setdefault('body', horse.get('market', {}).get('body_weight'))
            horse.setdefault('win', None)
            horse.setdefault('place', None)
            horse.setdefault('ticket_review', horse.get('comparison', {}).get('ticket_review', '未確認'))
            if horse.get('history_audit'):
                horse['history_audit'].setdefault('summary', horse['history_audit'].get('scope', '確認範囲は原文を参照'))
    return render_compact(d, json_name, {k:adapt_result(v) for k,v in (results or {}).items()})
