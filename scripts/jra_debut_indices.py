"""Experimental debut references from earlier, source-timestamped debut results.

No market input, current-race outcome, invented workout, or learned coefficients.
One historical starter contributes once even if sire, trainer and jockey all match.
"""
from copy import deepcopy
from datetime import datetime, date
from math import exp, isfinite
from statistics import mean, pstdev
import re, unicodedata

VERSION = 'jra-debut-cohort-v1'
ROLES = ('first', 'second', 'top2', 'top3')
WEIGHTS = {'sire': .4, 'trainer': .35, 'jockey': .25}

def normalized(value):
    s = unicodedata.normalize('NFKC', value or '')
    s = re.sub(r'^父[:：]', '', s)
    return re.sub(r'[\s△▲☆★◇]|\([^)]*\)', '', s)

def stamp(value):
    d = datetime.fromisoformat(value)
    if d.tzinfo is None:
        raise ValueError('資料時点にはタイムゾーンが必要')
    return d

def eligible_observations(observations, race, as_of):
    cutoff = stamp(as_of); today = date.fromisoformat(race['start_at'][:10])
    selected = []; omitted = []; seen = set()
    for x in observations:
        rid = x['observation_id']
        if rid in seen:
            continue
        seen.add(rid)
        day = date.fromisoformat(x['date'])
        reason = None
        if day >= today: reason = '当日以降の結果'
        elif (today-day).days > 730: reason = '730日より前'
        elif stamp(x['result_source']['retrieved_at']) > cutoff or stamp(x['card_source']['retrieved_at']) > cutoff: reason = '確認時点後の資料'
        elif x['surface'] != race['surface']: reason = '異なる馬場種別'
        elif not x.get('official_confirmed') or not x.get('rows_complete'): reason = '確定全頭結果ではない'
        elif (not isinstance(x['finish'], int) or isinstance(x['finish'], bool) or not isinstance(x['field'], int) or isinstance(x['field'], bool) or not 1 <= x['finish'] <= x['field'] <= 18): reason = '着順・頭数不正'
        elif not isinstance(x['distance_m'],int) or isinstance(x['distance_m'],bool) or not 0<x['distance_m']<=10000: reason = '距離不正'
        if reason: omitted.append({'observation_id': rid, 'reason': reason})
        else: selected.append(x)
    return selected, omitted

def apply_debut_indices(race, *, observations, as_of, computed_at=None):
    if '新馬' not in race.get('class_text', ''):
        raise ValueError('新馬専用の参考指標です')
    stamp(as_of); now = computed_at or datetime.now(stamp(as_of).tzinfo).isoformat(timespec='seconds')
    if not isinstance(race['distance_m'],int) or isinstance(race['distance_m'],bool) or not 0<race['distance_m']<=10000:
        raise ValueError('今回距離が不正')
    out = deepcopy(race); today = date.fromisoformat(race['start_at'][:10])
    cohort, omitted = eligible_observations(observations, race, as_of)
    active = [h for h in out['horses'] if h.get('status_at_snapshot') not in ('withdrawn', 'excluded')]
    for h in active:
        components = []
        own_id = (h.get('source_horse_id') or {}).get('id') or h.get('horse_id')
        for x in cohort:
            if own_id and str(x.get('horse_id')) == str(own_id):
                raise ValueError('新馬本人に以前の出走記録があり、初出走を要確認')
            matches = [k for k in WEIGHTS if normalized(h.get(k)) and normalized(h.get(k)) == normalized(x.get(k))]
            if not matches: continue
            association = sum(WEIGHTS[k] for k in matches)
            weight = association * exp(-(today-date.fromisoformat(x['date'])).days/180) / (1+abs(x['distance_m']-race['distance_m'])/400)
            # Subtract each race's field-size baseline; this is not a probability.
            f, n = x['finish'], x['field']
            residuals = {k: 100*((f == 1 if k == 'first' else f == 2 if k == 'second' else f <= (2 if k == 'top2' else 3)) - (1/n if k in ('first','second') else min(n,2 if k == 'top2' else 3)/n)) for k in ROLES}
            components.append(dict(x, matched_features=matches, association_weight=association, weight=weight, residuals=residuals))
        mass = sum(c['weight'] for c in components)
        ess = mass*mass/sum(c['weight']**2 for c in components) if mass else 0
        strength = min(mass, ess)/(min(mass, ess)+8) if mass else 0
        raw = {k: sum(c['weight']*c['residuals'][k] for c in components)/(mass+4) for k in ROLES}
        d = dict(version='jra-role-relative-v2', estimator_version=VERSION, method='debut_cohort_reference', label='新馬・関連実績参考' if components else '新馬・材料未充足', reason='同馬場の過去の新馬戦から父・厩舎・騎手が一致する出走例を比較。本人の実戦能力や調教状態の測定値ではない。複数一致でも同じ出走例は1回。' if components else '関連する保存新馬実績なし。比較の出発点50のみ。平均能力を確認した意味ではなく、順位差を作らない。', experimental=True, calibrated=False, probability=False, comparison_scope='within_race_and_role', unit='50基準・関連する過去新馬成績の比較、確率ではない', computed_at=now, input_cutoff_at=as_of, runs=0, matched_starters=len(components), effective_runs=ess, weighted_sample_mass=mass, reliability_weight=strength, confidence='薄', training_status='未採点', missing=['本人の実走', '同条件で比較可能な全頭調教時計・負荷', '母・きょうだいの網羅的成績'], feature_weights=WEIGHTS.copy(), smoothing_mass=4, components=components, source_refs=list(dict.fromkeys(c['result_source']['url'] for c in components)), target_card_source=race['source'], cohort_omitted=omitted)
        for k in ROLES: d[k] = dict(value=None, raw_value=raw[k], label={'first':'1着参考','second':'2着ちょうど参考','top2':'連対参考','top3':'3着内参考'}[k])
        h['role_indices'] = d
    for k in ROLES:
        raw = [h['role_indices'][k]['raw_value'] for h in active if h['role_indices']['matched_starters']]
        center, spread = (mean(raw), pstdev(raw)) if raw else (0., 0.)
        for h in active:
            d = h['role_indices']; z = max(-3.,min(3.,(d[k]['raw_value']-center)/spread)) if spread and d['matched_starters'] else 0
            d[k]['value'] = round(50+10*z*d['reliability_weight'],1)
            d[k]['reference'] = dict(center_raw=center, spread_raw=spread, horse_numbers=[x['number'] for x in active if x['role_indices']['matched_starters']], formula='関連実績の頭数基準差を平滑化し、同R相対差を資料量で抑制。材料なしは差を作らない50。')
    out.setdefault('analysis', {})['debut_index_review'] = dict(version=VERSION, input_cutoff_at=as_of, not_current_ability_measurement=True, market_used=False, training_scored=False, reason='初出走でも確認できる関連実績から数値参考を作る。調教や母系を確認できたことにはしない。')
    return out

def audit_debut(horse, race, fixed_at):
    d=horse['role_indices']; errors=[]
    try:
        valid = '新馬' in race.get('class_text','') and d['estimator_version']==VERSION and d['calibrated'] is False and d['probability'] is False
        valid = valid and stamp(d['input_cutoff_at']) <= stamp(d['computed_at']) <= stamp(fixed_at)
        components=d['components']; valid=valid and len({x['observation_id'] for x in components})==len(components)
        eligible,_=eligible_observations(components,race,d['input_cutoff_at']); valid=valid and len(eligible)==len(components)
        valid=valid and all(all(normalized(horse.get(k)) and normalized(horse.get(k))==normalized(c.get(k)) for k in c['matched_features']) and c['matched_features'] and 0<c['weight']<=1 for c in components)
        valid=valid and all(isinstance(d[k]['value'],(int,float)) and not isinstance(d[k]['value'],bool) and isfinite(d[k]['value']) and 0<d[k]['value']<100 for k in ROLES)
        valid=valid and d['matched_starters']==len(components) and d['training_status']=='未採点'
        valid=valid and all(c['result_source'].get('raw_sha256') and c['card_source'].get('raw_sha256') for c in components)
        valid=valid and (bool(components) or all(d[k]['value']==50 for k in ROLES))
    except (KeyError,TypeError,ValueError,ZeroDivisionError): valid=False
    if not valid: errors.append(('debut_evidence_invalid',horse['number'],'新馬参考の関連実績・時点・対象・非確率表示を確認。'))
    return errors
