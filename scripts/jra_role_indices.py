"""Four descriptive performance indices. No fitting, outcome input or calibrated probabilities."""
from copy import deepcopy
from datetime import date, datetime
from math import exp, sqrt, isfinite
from statistics import mean, pstdev
import re, unicodedata
from urllib.parse import urlparse, parse_qs, unquote

VERSION='jra-role-relative-v2'
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

def clip(x):
    if not isinstance(x,(int,float)) or isinstance(x,bool) or not isfinite(x):raise ValueError('非有限値・数値以外は採点できません')
    return max(0.,min(100.,x))

def horse_evidence_refs(horse):
    refs=set(horse.get('evidence_refs',[]));d=horse.get('role_indices',{})
    if d.get('version')==VERSION and d.get('method') in ('same_surface_history','cross_surface_reference'):
        refs.update(c['run_id'] for c in d.get('components',[]))
    return refs

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
    if history is not None and (history.get('status')!='parsed' or not isinstance(history.get('prior_races'),list)):
        raise ValueError('全掲載戦歴の解析済み表が必要。好走補足だけでは代替できません')
    known={run_key(p.get('run_id') or p.get('source')):p for p in horse.get('past',[])}
    all_rows=[]
    # The full table includes poor performances too. Selected good supplements alone
    # must not become the history denominator.
    for p in (history or {}).get('prior_races',[]):
        key=run_key(p.get('result_url'));rich=known.get(key)
        if rich:all_rows.append(rich);continue
        cells=p.get('source_row',[]);raw=p.get('finish_raw','')
        all_rows.append(dict(iso_date=p.get('date'),venue=p.get('venue'),resolved_class=((p.get('grade_raw') or '')+' '+(p.get('race_name') or '')),surface=p.get('surface'),distance=p.get('distance'),finish=int(raw) if str(raw).isdigit() else None,field=int(cells[5]) if len(cells)>5 and str(cells[5]).isdigit() else None,gap=None,condition=p.get('going'),run_id=p.get('result_url')))
    all_rows.extend(p for p in horse.get('past',[]) if not p.get('supplemental') or history)
    seen=set();valid=[];omitted=[]
    for p in all_rows:
        key=run_key(p.get('run_id') or p.get('source'))
        if not key or key in seen:continue
        seen.add(key);day=p.get('iso_date')
        if not day:omitted.append(dict(run_id=key,reason='日付未確認'));continue
        class_source=p.get('class_source')
        if isinstance(class_source,dict) and class_source.get('retrieved_at'):
            p=dict(p);p['_class_checked_at']=class_source['retrieved_at']
        age=(today-date.fromisoformat(day)).days
        if age<=0:raise ValueError('当日以降の結果を指標へ混ぜられません: '+key)
        lev=level(p.get('resolved_class'));surface=SURFACES.get(p.get('surface'))
        f,n,dist,gap=p.get('finish'),p.get('field'),p.get('distance'),p.get('gap')
        integer=lambda v:isinstance(v,int) and not isinstance(v,bool)
        numeric=lambda v:isinstance(v,(int,float)) and not isinstance(v,bool) and isfinite(v)
        reason='730日より前' if age>730 else 'JRA以外の級比較は未検証' if p.get('venue') not in JRA else '級未確認' if lev is None else '完走着順・頭数・距離不正' if not integer(f) or not integer(n) or not 1<=f<=n<=18 or not integer(dist) or not 0<dist<=10000 else '着差不正' if gap is not None and (not numeric(gap) or (f>1 and gap<0)) else '種別未確認' if surface is None else None
        if reason:omitted.append(dict(run_id=key,reason=reason));continue
        valid.append(dict(run_id=p.get('run_id') or p.get('source'),date=day,age_days=age,venue=p['venue'],surface=surface,distance=p['distance'],finish=p['finish'],field=p['field'],gap=p.get('gap'),going=p.get('condition'),level=lev,class_text=p.get('resolved_class'),margin_missing=p.get('gap') is None,class_checked_at=p.get('_class_checked_at')))
    return valid,omitted

def apply_indices(race,*,as_of,history_by_number=None,computed_at=None):
    """Copy a race; preserve marks, old scores, ranks and ticket plans exactly."""
    out=deepcopy(race);today=date.fromisoformat(race['start_at'][:10]);stamp=datetime.fromisoformat(as_of)
    if stamp.tzinfo is None:raise ValueError('入力確認時点にタイムゾーンが必要')
    if not isinstance(race.get('distance_m'),int) or isinstance(race['distance_m'],bool) or not 0<race['distance_m']<=10000:raise ValueError('今回距離が不正')
    current=level(race.get('grade') or race.get('class_text'));surface=SURFACES.get(race['surface']);history_by_number=history_by_number or {}
    for h in out['horses']:
        history=history_by_number.get(h['number']);src=(history or {}).get('source')
        if history and ((history.get('number') is not None and history['number']!=h['number']) or (history.get('name') and history['name']!=h.get('name')) or (history.get('key') and race.get('key') and history['key']!=race['key'])):
            raise ValueError('別の馬・レースの掲載履歴が混入しています')
        if src and datetime.fromisoformat(src['retrieved_at'])>stamp:raise ValueError('確認時点より後の履歴です')
        base=dict(version=VERSION,calibrated=False,experimental=True,computed_at=computed_at or datetime.now(stamp.tzinfo).isoformat(timespec='seconds'),input_cutoff_at=as_of,probability=False,unit='同じレース・同じ役割の50基準の相対実績比較。確率ではない',comparison_scope='within_race_and_role',source_refs=[],components=[],omitted_runs=[],confidence='未評価')
        status=h.get('status_at_snapshot')
        if status in ('withdrawn','excluded'):
            base.update(method='not_applicable',label='取消・除外',reason='購入候補外。0点にしない。')
            values={k:None for k in ROLES}
        elif h.get('score_method')=='market_reference' or '新馬' in (race.get('class_text') or ''):
            base.update(method='not_computed',label='新馬・独自指標なし',reason='実走なし。市場参考値は別欄に保持し、4指標を捏造しない。')
            values={k:None for k in ROLES}
        else:
            runs,omitted=normal_runs(h,history,today);base['omitted_runs']=omitted
            if any(p.get('class_checked_at') and datetime.fromisoformat(p['class_checked_at'])>stamp for p in runs):raise ValueError('入力確認時点より後の級情報が含まれています')
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
                freshness=exp(-min(p['age_days'] for p in chosen)/365)
                reliability=ess/(ess+3)*freshness*(1 if same else .25)
                base.update(method=method,label=('障害実走参考' if surface=='hurdle' else '同種馬場実績') if same else '異馬場参考',reason='全掲載履歴のうち条件を満たす直近8走まで。古い好走だけを選ばず、1走1回集約。' if same else '今回種別の実走なし。他の平地種別の実績を参考表示。今回条件への適応を保証しない。',confidence='薄' if reliability<.4 else '中',effective_runs=round(ess,2),runs=len(chosen),reliability_weight=round(reliability,8),reliability_definition='有効走数/(有効走数+3)×最新走の経過日数補正。異馬場はさらに1/4。未学習の抑制係数で、信頼確率ではない。',components=components,source_refs=list(dict.fromkeys(c['run_id'] for c in components)),full_history_used=bool(history))
            else:
                # A market fallback remains explicitly separate from performance indices.
                market=h.get('market',{});odds=market.get('win');ms=market.get('source')
                if isinstance(odds,(int,float)) and not isinstance(odds,bool) and isfinite(odds) and odds>0 and ms and datetime.fromisoformat(ms['retrieved_at'])<=stamp:
                    values={k:None for k in ROLES}
                    base.update(method='market_reference',label='市場参考のみ',market_reference=dict(value=odds,label='保存単勝オッズ',source=ms),reason='独自実績の比較は未解決。保存単勝オッズを別欄へ表示し、4役割の数値へコピーしない。',source_refs=[ms['url']],confidence='資料不足')
                else:
                    values={k:None for k in ROLES};base.update(method='not_computed',label='資料不足',reason='比較可能な完走・級または時点付き市場データなし。欠損を0点にしない。')
        for k,label in ROLES.items():base[k]=dict(value=None,raw_value=values[k],label=label)
        h['role_indices']=base
    # Compare only independently usable runners in this race, then shrink weak
    # evidence towards the reference. Do not re-normalize after shrinking: doing
    # so would undo the suppression when every runner has only one observation.
    comparable=[h for h in out['horses'] if h['role_indices']['method']=='same_surface_history']
    reference_pool=comparable or [h for h in out['horses'] if h['role_indices']['method']=='cross_surface_reference']
    for k in ROLES:
        raw=[h['role_indices'][k]['raw_value'] for h in reference_pool]
        center,spread=(mean(raw),pstdev(raw)) if raw else (None,None)
        for h in out['horses']:
            d=h['role_indices'];value=d[k]['raw_value']
            if value is None:continue
            z=max(-3.,min(3.,(value-center)/spread)) if spread else 0.
            d[k]['value']=round(50+10*z*d['reliability_weight'],1)
            d[k]['reference']=dict(center_raw=center,spread_raw=spread,horse_numbers=[x['number'] for x in reference_pool],formula='50+10×相対差（±3まで）×資料量補正。補正後の再標準化はしない。')
    out.setdefault('analysis',{})['role_index_version']=VERSION
    return out

def audit_indices(race,fixed_at):
    errors=[];before=datetime.fromisoformat(fixed_at)
    for h in race['horses']:
        d=h.get('role_indices',{});n=h['number']
        if d.get('version')!=VERSION:errors.append(('role_indices_missing',n,'4役割指標の定義・計算記録が必要。'));continue
        try:valid_time=datetime.fromisoformat(d['input_cutoff_at'])<=datetime.fromisoformat(d['computed_at'])<=before
        except (ValueError,KeyError,TypeError):valid_time=False
        roles_present=all(isinstance(d.get(k),dict) and 'value' in d[k] and 'raw_value' in d[k] for k in ROLES)
        vals=[d.get(k,{}).get('value') for k in ROLES]
        if not valid_time or not d.get('reason') or d.get('calibrated') is not False or d.get('probability') is not False:errors.append(('role_indices_definition_missing',n,'時点・根拠・未校正表示が必要。'))
        if not roles_present or any(v is not None and (not isinstance(v,(float,int)) or isinstance(v,bool) or not isfinite(v) or not 0<v<100) for v in vals):errors.append(('role_indices_invalid',n,'4項目と0/100を含まない相対指数、または理由付き欠損を保存。'))
        method=d.get('method')
        if method not in ['same_surface_history','cross_surface_reference','not_computed','not_applicable','market_reference']:errors.append(('role_index_method_invalid',n,'指標と参考・欠損の区分が不正。'))
        if method=='market_reference' and (any(v is not None for v in vals) or not d.get('market_reference')):errors.append(('market_as_performance_index',n,'市場参考値を独自4指標へコピーしない。'))
        if method in ('same_surface_history','cross_surface_reference'):
            components=d.get('components',[]);refs=d.get('source_refs',[])
            try:
                valid=bool(components and refs and len(refs)==len(set(refs)) and len({run_key(c['run_id']) for c in components})==len(components))
                valid=valid and all(date.fromisoformat(c['date'])<date.fromisoformat(race['start_at'][:10]) and c.get('class_text') and level(c['class_text'])==c['level'] and isinstance(c['weight'],(int,float)) and isfinite(c['weight']) and c['weight']>0 for c in components)
                valid=valid and set(refs)=={c['run_id'] for c in components} and all(v is not None for v in vals)
                valid=valid and 0<d['reliability_weight']<1 and d.get('comparison_scope')=='within_race_and_role'
                valid=valid and all(d[k].get('reference') and isinstance(d[k]['raw_value'],(int,float)) and isfinite(d[k]['raw_value']) and 0<=d[k]['raw_value']<=100 for k in ROLES)
            except (KeyError,ValueError,TypeError):valid=False
            if not valid:errors.append(('role_index_evidence_missing',n,'当日より前の実走・級・寄与・資料量補正・相手比較が必要。'))
    return errors
