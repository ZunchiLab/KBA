"""Conservative, experimental race-day changes to a frozen JRA forecast."""
from datetime import datetime
from math import log

VERSION = 'race-day-review-v1'


def _stamp(value):
    return datetime.fromisoformat(value) if value else None


def _odds(value):
    return isinstance(value, (float, int)) and value > 0


def _jockey(value):
    return ''.join((value or '').split())


def _style(position, count):
    if not isinstance(position, int) or position < 1 or position > count:
        return None
    relative = (position - 1) / max(1, count - 1)
    return '逃げ' if position == 1 else '先行' if relative <= .38 else '差し' if relative <= .70 else '追込'


def observations(data, races, target, cutoff):
    """Use only confirmed earlier results from the same venue and surface."""
    by_number = {r['race_no']: r for r in races}
    rows, sources = [], []
    for result in data['races']:
        original = by_number.get(result['race_no'])
        source = result.get('source') or {}
        checked = _stamp(source.get('retrieved_at'))
        if (not original or original['surface'] != target['surface']
                or result['status'] != 'confirmed' or not checked or checked > cutoff
                or _stamp(original['start_at']) >= _stamp(target['start_at'])):
            continue
        started = [h for h in result['rows'] if h['runner_status'] not in ('withdrawn','excluded')]
        original_horses = {h['number']: h for h in original['horses']}
        sources.append(dict(race_no=result['race_no'], retrieved_at=source['retrieved_at'], raw_sha256=source.get('raw_sha256')))
        for row in started:
            try:
                pop = int(row.get('final_popularity'))
            except (TypeError, ValueError):
                continue
            frame = row.get('frame') or original_horses.get(row['number'], {}).get('frame')
            corners = row.get('corners') or []
            finish = row.get('finish')
            rows.append(dict(race=result['race_no'], pop=pop, placed=isinstance(finish,int) and finish <= 3,
                             style=_style(corners[0],len(started)) if corners else None,
                             frame=frame, side='内' if isinstance(frame,int) and frame<=4 else '外' if isinstance(frame,int) and frame<=8 else None,
                             jockey=_jockey(row.get('jockey')) or None))
    return rows, sources


def trend_signal(rows, field, value, min_count, min_races, strength):
    """Compare 3rd-or-better rates to the other runners in the same popularity band."""
    if value is None:
        return None
    pool = [row for row in rows if row[field] is not None]
    group = [row for row in pool if row[field] == value]
    other = [row for row in pool if row[field] != value]
    if len(group) < min_count or len({row['race'] for row in group}) < min_races:
        return None
    expected = 0.0
    for row in group:
        band = [peer for peer in other if (peer['pop'] <= 3) == (row['pop'] <= 3)]
        if len(band) < 4:
            return None
        expected += sum(peer['placed'] for peer in band) / len(band)
    hits = sum(row['placed'] for row in group)
    difference = (hits - expected) / len(group)
    weight = strength if difference >= .18 else -strength if difference <= -.18 else 0.0
    return dict(field=field,group=value,starts=len(group),races=len({row['race'] for row in group}),
                placed=hits,expected_placed=round(expected,2),difference=round(difference,3),weight=weight)


def create_revision(race, data, races, snapshot, calculated_at):
    """Save only prospective, timestamped rankings. The morning forecast is immutable."""
    cutoff = _stamp(calculated_at)
    if cutoff >= _stamp(race['start_at']) or _stamp(snapshot['checked_at']) > cutoff:
        return None
    morning = sorted((h for h in race['horses'] if h.get('rank')),key=lambda h:h['rank'])
    fresh = {h['number']: h for h in snapshot['runners']}
    if set(fresh) != {h['number'] for h in race['horses']}:
        return None
    active = [h for h in morning if fresh[h['number']]['status']=='出走']
    removed = [h['number'] for h in morning if fresh[h['number']]['status']!='出走']
    if not active:
        return None
    # Normalise inverse decimal odds over a common field, even after withdrawals.
    comparable = [h for h in active if _odds(h.get('odds')) and _odds(fresh[h['number']].get('win'))]
    old_sum = sum(1/h['odds'] for h in comparable)
    new_sum = sum(1/fresh[h['number']]['win'] for h in comparable)
    market_valid = len(comparable)==len(active) and len(active)>=2
    market_mode = race['class_text']=='新馬'
    eligible = race['surface'] in ('turf','dirt') and not market_mode
    rows, result_sources = observations(data, races, race, cutoff) if eligible else ([],[])
    enough_results = len(result_sources) >= 3
    evidence = {}
    for i,horse in enumerate(active):
        number = horse['number']
        update = fresh[number]
        factors = []
        if market_valid:
            ratio = (horse['odds']/update['win'])*(old_sum/new_sum)
            movement = log(ratio)
            contribution = (.85 if movement>=log(1.40) else -.85 if movement<=-log(1.40)
                            else .35 if movement>=log(1.18) else -.35 if movement<=-log(1.18) else 0)
            factors.append(dict(field='market',group='単勝支持率の変化',ratio=round(ratio,3),
                                morning_odds=horse['odds'],latest_odds=update['win'],weight=contribution if eligible else 0))
        if enough_results:
            frame = horse.get('frame')
            side = '内' if isinstance(frame,int) and frame<=4 else '外' if isinstance(frame,int) and frame<=8 else None
            # The broad and individual gate comparisons share observations.
            frame_result = trend_signal(rows,'frame',frame,5,3,.30) or trend_signal(rows,'side',side,10,3,.30)
            for signal in (trend_signal(rows,'style',horse.get('style'),6,2,.40),
                           frame_result,trend_signal(rows,'jockey',_jockey(update.get('jockey')) or None,4,3,.30)):
                if signal:
                    factors.append(signal)
        total = round(max(-1.25,min(1.25,sum(f['weight'] for f in factors))),3)
        evidence[number] = dict(number=number,morning_rank=horse['rank'],base_rank=i+1,
                                correction=total,comparison_value=round(i+1-total,3),factors=factors)
    if market_mode and market_valid:
        # Debut races remain explicitly separate market references.
        ordered = sorted(active,key=lambda h:(fresh[h['number']]['win'],h['rank']))
    elif eligible:
        ordered = sorted(active,key=lambda h:(evidence[h['number']]['comparison_value'],h['rank']))
    else:
        ordered = active
    order = [h['number'] for h in ordered]
    morning_marked = [h for h in morning if h['number'] in race['analysis'].get('mark_selection',{}).get('marked_numbers',[])]
    surviving_marks = sum(h['number'] not in removed for h in morning_marked)
    mark_slots = [h['mark'] for h in morning_marked[:surviving_marks]]
    marks = {str(n):mark_slots[i] if i<len(mark_slots) else '無印' for i,n in enumerate(order)}
    changes = []
    for i,n in enumerate(order):
        row = evidence[n]
        row['rank'] = i+1
        if row['morning_rank'] != i+1:
            changes.append(dict(number=n,from_rank=row['morning_rank'],to_rank=i+1))
    main = next((p for p in race['bet_plans'] if p['selected_for_example']),None)
    live_tickets = []
    if main:
        # Reconsider only the explicitly evaluated morning combinations. No new
        # ticket or greater stake is inferred from the revised order.
        marked = {n for n in order if marks[str(n)]!='無印'}
        anchors = set(order[:2] if main['kind']=='quinella' else order[:1])
        retained = [t for t in snapshot['tickets'] if set(t['numbers'])<=marked and set(t['numbers']) & anchors]
        if retained and all(t.get('lower') is not None and t['lower']>=t['minimum'] for t in retained):
            live_tickets = retained
    decision = '条件達成' if live_tickets else '見送り'
    return dict(version=VERSION,calculated_at=calculated_at,source_checked_at=snapshot['checked_at'],
                mode='市場参考' if market_mode else '試験的な順位補正' if eligible else '比較保留',
                order=order,marks=marks,withdrawn=removed,changes=changes,horse_evidence=list(evidence.values()),
                same_surface_results=result_sources,trend_used=enough_results,market_comparable=market_valid,
                main_review=dict(decision=decision,kind=main['kind'] if main else None,tickets=live_tickets,
                                 reason='朝に比較した組合せの範囲で修正印の軸・候補と現在価格を確認。' if live_tickets else '朝の本線がない、または修正印・候補・全点価格条件を満たす構成なし。'),
                limitations='順位の限定的な補正。補正幅・閾値は未校正、的中率向上は未検証。市場と当日傾向には相関がある。全頭の調教・状態は未評価。')
