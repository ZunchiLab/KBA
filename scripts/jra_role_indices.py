"""Four descriptive performance indices. No fitting, outcome input or calibrated probabilities."""
from copy import deepcopy
from datetime import date, datetime
from math import exp, sqrt
import re, unicodedata
from urllib.parse import urlparse, parse_qs, unquote

VERSION='jra-role-performance-v1'
START_DATE='2026-11-01'
ROLES={'first':'1着指数','second':'2着ちょうど指数','top2':'連対指数（2着以内）','top3':'3着内指数'}
JRA={'札幌','函館','福島','新潟','東京','中山','中京','京都','阪神','小倉'}
SURFACES={'芝':'turf','ダ':'dirt','障':'hurdle','turf':'turf','dirt':'dirt','hurdle':'hurdle'}

def level(text):
    s=unicodedata.normalize('NFKC',text or '')
    if 'Jpn' in s:return None
    for token,value in [('GIII',5),('GII',6),('GI',7),('リステッド',4),('オープン',4),('OP',4),('3勝',3),('2勝',2),('1勝',1),('未勝利',0),('新馬',0)]:
        if token in s:return value
    return None

def run_key(url):
    return unquote(parse_qs(urlparse(url or '').query).get('CNAME',[url or ''])[0])

def clip(x):return max(0.,min(100.,x))

def per_run(p,current_level):
    f,n=p['finish'],p['field'];ordinal=clip(100-75*(f-1)/max(1,n-1))
    gap=p.get('gap')
    margin=100. if f==1 else 100*exp(-max(0,gap)/(.55*sqrt(p['distance']/1200))) if gap is not None else None
    # Distinct targets, so a frequent runner-up need not share the winning order.
    target2=100*exp(-abs(f-2)/max(1,n/5))
    within2=100*exp(-max(0,f-2)/max(1,n/4))
    within3=100*exp(-max(0,f-3)/max(1,n/3))
    adjust=max(-36,min(10,(p['level']-current_level)*(12 if p['level']<current_level else 4)))
    values={'first':(.75*margin+.25*ordinal) if margin is not None else ordinal,
            'second':target2,
            'top2':(.4*margin+.6*within2) if margin is not None else within2,
            'top3':(.2*margin+.8*within3) if margin is not None else within3}
    return {k:clip(v+adjust) for k,v in values.items()}

def normal_runs(horse,history,today):
    known={run_key(p.get('run_id') or p.get('source')):p for p in horse.get('past',[])}
    all_rows=[]
    # The full table includes poor performances too. Selected good supplements alone
    # must not become the history denominator.
    for p in (history or {}).get('prior_races',[]):
        key=run_key(p.get('result_url'));rich=known.get(key)
        if rich:all_rows.append(rich);continue
        cells=p.get('source_row',[]);raw=p.get('finish_raw','')
        all_rows.append(dict(iso_date=p.get('date'),venue=p.get('venue'),resolved_class=(p.get('grade_raw','')+' '+p.get('race_name','')),surface=p.get('surface'),distance=p.get('distance'),finish=int(raw) if str(raw).isdigit() else None,field=int(cells[5]) if len(cells)>5 and str(cells[5]).isdigit() else None,gap=None,condition=p.get('going'),run_id=p.get('result_url')))
    all_rows.extend(p for p in horse.get('past',[]) if not p.get('supplemental') or history)
    seen=set();valid=[];omitted=[]
    for p in all_rows:
        key=run_key(p.get('run_id') or p.get('source'))
        if not key or key in seen:continue
        seen.add(key);day=p.get('iso_date')
        if not day:omitted.append(dict(run_id=key,reason='日付未確認'));continue
        age=(today-date.fromisoformat(day)).days
        if age<=0:raise ValueError('当日以降の結果を指標へ混ぜられません: '+key)
        lev=level(p.get('resolved_class'));surface=SURFACES.get(p.get('surface'))
        reason='730日より前' if age>730 else 'JRA以外の級比較は未検証' if p.get('venue') not in JRA else '級未確認' if lev is None else '完走着順・頭数・距離未確認' if not isinstance(p.get('finish'),int) or not isinstance(p.get('field'),int) or p['finish']<1 or p['field']<p['finish'] or not p.get('distance') else '種別未確認' if surface is None else None
        if reason:omitted.append(dict(run_id=key,reason=reason));continue
        valid.append(dict(run_id=p.get('run_id') or p.get('source'),date=day,age_days=age,venue=p['venue'],surface=surface,distance=p['distance'],finish=p['finish'],field=p['field'],gap=p.get('gap'),going=p.get('condition'),level=lev,class_text=p.get('resolved_class'),margin_missing=p.get('gap') is None))
    return valid,omitted

def apply_indices(race,*,as_of,history_by_number=None,computed_at=None):
    """Copy a race; preserve marks, old scores, ranks and ticket plans exactly."""
    out=deepcopy(race);today=date.fromisoformat(race['start_at'][:10]);stamp=datetime.fromisoformat(as_of)
    current=level(race.get('grade') or race.get('class_text'));surface=SURFACES.get(race['surface']);history_by_number=history_by_number or {}
    for h in out['horses']:
        history=history_by_number.get(h['number']);src=(history or {}).get('source')
        if src and datetime.fromisoformat(src['retrieved_at'])>stamp:raise ValueError('確認時点より後の履歴です')
        base=dict(version=VERSION,calibrated=False,computed_at=computed_at or datetime.now(stamp.tzinfo).isoformat(timespec='seconds'),input_cutoff_at=as_of,probability=False,unit='0–100の実績比較。的中確率ではない',source_refs=[],components=[],omitted_runs=[],confidence='未評価')
        status=h.get('status_at_snapshot')
        if status in ('withdrawn','excluded'):
            base.update(method='not_applicable',label='取消・除外',reason='購入候補外。0点にしない。')
            values={k:None for k in ROLES}
        elif h.get('score_method')=='market_reference' or '新馬' in (race.get('class_text') or ''):
            base.update(method='not_computed',label='新馬・独自指標なし',reason='実走なし。市場参考値は別欄に保持し、4指標を捏造しない。')
            values={k:None for k in ROLES}
        else:
            runs,omitted=normal_runs(h,history,today);base['omitted_runs']=omitted
            if surface=='hurdle':runs=[p for p in runs if p['surface']=='hurdle']
            same=[p for p in runs if p['surface']==surface]
            pool=same or ([p for p in runs if p['surface'] in ('turf','dirt')] if surface!='hurdle' else [])
            chosen=sorted(pool,key=lambda p:(p['age_days'],p['run_id']))[:8]
            if chosen and current is not None:
                method='same_surface_history' if same else 'cross_surface_reference'
                weights=[];components=[]
                for p in chosen:
                    w=exp(-p['age_days']/180)/(1+abs(p['distance']-race['distance_m'])/800)*(1.15 if p['venue']==race['venue'] else 1)
                    vals=per_run(p,current);weights.append(w);components.append(p|dict(weight=round(w,8),values={k:round(v,4) for k,v in vals.items()}))
                values={k:round(sum(c['values'][k]*w for c,w in zip(components,weights))/sum(weights),1) for k in ROLES}
                ess=sum(weights)**2/sum(w*w for w in weights)
                base.update(method=method,label='同種馬場実績' if same else '異馬場参考',reason='全掲載履歴のうち条件を満たす直近8走まで。古い好走だけを選ばず、1走1回集約。' if same else '今回種別の実走なし。他の平地種別の実績を参考表示。今回条件への適応を保証しない。',confidence='低' if not same or ess<2 or min(p['age_days'] for p in chosen)>180 else '中',effective_runs=round(ess,2),runs=len(chosen),components=components,source_refs=list(dict.fromkeys(c['run_id'] for c in components)),full_history_used=bool(history))
            else:
                # A market fallback remains explicitly separate from performance indices.
                market=h.get('market',{});odds=market.get('win');ms=market.get('source')
                if odds and ms and datetime.fromisoformat(ms['retrieved_at'])<=stamp:
                    all_odds=[x.get('market',{}).get('win') for x in out['horses'] if x.get('status_at_snapshot')=='declared' and x.get('market',{}).get('win')]
                    ref=round(100*min(all_odds)/odds,1);values={k:ref for k in ROLES}
                    base.update(method='market_reference',label='市場参考・4役割未分離',reason='独自の級・実走比較が未解決。100×当該レース最小単勝÷保存単勝の共通参考値。4役割の違いを推定した数値ではない。',source_refs=[ms['url']],confidence='低')
                else:
                    values={k:None for k in ROLES};base.update(method='not_computed',label='資料不足',reason='比較可能な完走・級または時点付き市場データなし。欠損を0点にしない。')
        for k,label in ROLES.items():base[k]=dict(value=values[k],label=label)
        h['role_indices']=base
    out.setdefault('analysis',{})['role_index_version']=VERSION
    return out

def audit_indices(race,fixed_at):
    errors=[];before=datetime.fromisoformat(fixed_at)
    for h in race['horses']:
        d=h.get('role_indices',{});n=h['number']
        if d.get('version')!=VERSION:errors.append(('role_indices_missing',n,'4役割指標の定義・計算記録が必要。'));continue
        try:valid_time=datetime.fromisoformat(d['input_cutoff_at'])<=datetime.fromisoformat(d['computed_at'])<=before
        except (ValueError,KeyError,TypeError):valid_time=False
        vals=[d.get(k,{}).get('value') for k in ROLES]
        if not valid_time or not d.get('reason') or d.get('calibrated') is not False or d.get('probability') is not False:errors.append(('role_indices_definition_missing',n,'時点・根拠・未校正表示が必要。'))
        if any(v is not None and (not isinstance(v,(float,int)) or isinstance(v,bool) or not 0<=v<=100) for v in vals):errors.append(('role_indices_invalid',n,'0〜100の数値または理由付き欠損を保存。'))
        if d.get('method') in ('same_surface_history','cross_surface_reference') and (not d.get('components') or not d.get('source_refs') or any(c['date']>=race['start_at'][:10] for c in d['components'])):errors.append(('role_index_evidence_missing',n,'当日より前の実走・入力・寄与が必要。'))
    return errors
