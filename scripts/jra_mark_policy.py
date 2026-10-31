"""Prospective mark budget. Selection stays a human decision; scores never change."""
from copy import deepcopy
from datetime import datetime
from math import ceil
from jra_role_indices import horse_evidence_refs

POLICY = 'field-size-v1'
COVERAGE_POLICY = 'coverage-first-v2'
COVERAGE_START = '2026-11-01'
START_DATE = '2026-10-26'
SYMBOLS = ('◎','○','▲','△','△','△','注','注')
MARKS = set('◎○▲☆△注')

def active_horses(race):
    return [h for h in race['horses'] if h.get('status_at_snapshot') not in ('withdrawn','excluded')]

def suggested_limit(field_size, policy=POLICY):
    if not isinstance(field_size,int) or isinstance(field_size,bool) or not 0<=field_size<=18:
        raise ValueError('JRAの出走予定頭数0〜18が必要')
    return min(field_size,max(3 if policy==COVERAGE_POLICY else 2,ceil(field_size/3)))

def has_mark(horse):
    return any(c in MARKS for c in horse.get('mark',''))

def apply(race, numbers, *, reviewed_at, reason, boundary_reviews, exception_reason=None, coverage_review=None):
    """Return a copy. Caller explicitly selects horses and reviews the boundary.

    Never selects a prefix, inserts a horse to fill a quota, or alters tickets.
    Over-limit exceptions remain visible and need an explanation.
    """
    result=deepcopy(race); active=active_horses(result); known={h['number'] for h in active}
    chosen=list(numbers)
    if len(chosen)!=len(set(chosen)) or not set(chosen)<=known:
        raise ValueError('印候補は出走予定馬の重複しない馬番で指定')
    if not reason or datetime.fromisoformat(reviewed_at)>=datetime.fromisoformat(result['start_at']):
        raise ValueError('発走前の判断時刻と選定理由が必要')
    policy=COVERAGE_POLICY if result['start_at'][:10]>=COVERAGE_START else POLICY
    limit=suggested_limit(len(active),policy)
    if policy==COVERAGE_POLICY and chosen and not coverage_review:
        raise ValueError('馬券内3頭の捕捉を目的に4役割・別展開・印外リスクを比較する')
    if len(chosen)>limit and not exception_reason:
        raise ValueError('目安超過には削れない根拠・買い目の費用を含む例外理由が必要')
    chosen_set=set(chosen)
    main_pool={n for p in result.get('bet_plans',[]) if p.get('selected_for_example') for t in p['tickets'] for n in t['numbers']}
    if not main_pool<=chosen_set:
        raise ValueError('本線に無印の馬が残る。印か買い目を人手で再検討する')
    if policy==COVERAGE_POLICY and main_pool and len(chosen)<min(3,len(active)):
        raise ValueError('本線2頭に絞っても印候補は馬券内3頭を比較する')
    ordered=sorted((h for h in active if h['number'] in chosen_set),key=lambda h:(h.get('rank') is None,h.get('rank') or 999,h['number']))
    symbols=SYMBOLS if policy==POLICY else SYMBOLS+('注',)*10
    if len(ordered)>len(symbols):
        raise ValueError('この方式で扱える印頭数を超えている')
    mapping={h['number']:symbols[i] for i,h in enumerate(ordered)}
    for h in active:
        prefix='参考' if h.get('score_method')=='market_reference' else '暫定' if result.get('surface') in ('障','hurdle') else ''
        h['mark']=prefix+mapping[h['number']] if h['number'] in mapping else '無印'
    result.setdefault('analysis',{})['mark_selection']={
        'policy':policy,'field_size_at_review':len(active),'suggested_limit':limit,
        'marked_numbers':[h['number'] for h in ordered], 'reviewed_at':reviewed_at,
        'reason':reason,'boundary_reviews':deepcopy(boundary_reviews),
        'exception_reason':exception_reason,'purpose':('3頭捕捉を優先する印の参考数。購入点数とは別。' if policy==COVERAGE_POLICY else '印と本線候補を絞る目安。')+'的中確率や最適頭数の推定ではない。',
    }
    if coverage_review is not None:result['analysis']['mark_selection']['coverage_review']=deepcopy(coverage_review)
    return result

def audit_race(race, fixed_at):
    errors=[]; a=race.get('analysis',{}).get('mark_selection',{});active=active_horses(race)
    known={h['number']:h for h in active};actual={h['number'] for h in active if has_mark(h)}
    policy=COVERAGE_POLICY if race['start_at'][:10]>=COVERAGE_START else POLICY
    if a.get('policy')!=policy:
        return [('mark_selection_missing',None,'出走頭数に応じた印候補・境界比較をanalysis.mark_selectionへ発走前保存する。')]
    if a.get('field_size_at_review')!=len(active) or a.get('suggested_limit')!=suggested_limit(len(active),policy):
        errors.append(('mark_field_size_mismatch',None,'取消・除外を除いた出走予定頭数と印の目安が不一致。'))
    numbers=a.get('marked_numbers',[])
    if len(numbers)!=len(set(numbers)) or set(numbers)!=actual or not set(numbers)<=set(known):
        errors.append(('mark_numbers_mismatch',None,'印の実表示と記録が一致しない。'))
    try:
        stamp=datetime.fromisoformat(a['reviewed_at'])
        valid=stamp<=datetime.fromisoformat(fixed_at) and stamp<datetime.fromisoformat(race['start_at'])
    except (ValueError,TypeError,KeyError):valid=False
    if not valid or not a.get('reason'):
        errors.append(('mark_selection_time_or_reason_missing',None,'予想固定以前・発走前の確認時刻と印選定理由が必要。'))
    if len(actual)>suggested_limit(len(active),policy) and not a.get('exception_reason'):
        errors.append(('mark_limit_exception_missing',None,'印の目安超過は、削れない根拠・増える点数費用を明記する。'))
    main_pool={n for p in race.get('bet_plans',[]) if p.get('selected_for_example') for t in p['tickets'] for n in t['numbers']}
    if not main_pool<=actual:
        errors.append(('main_horse_unmarked',None,'本線の無印馬を解消する。別案は本線と分け、印数を自動増加させない。'))
    if policy==COVERAGE_POLICY:
        c=a.get('coverage_review',{})
        if main_pool and len(actual)<min(3,len(active)):
            errors.append(('top3_mark_pool_too_small',None,'点数を絞る本線と、3頭を捕捉する印の範囲を分ける。'))
        if actual:
            groups=c.get('candidate_groups',{})
            valid=c.get('objective')=='capture_all_top3' and c.get('not_guaranteed') is True and c.get('reason')
            valid=valid and all(isinstance(groups.get(k),list) and groups[k] and set(groups[k])<=set(known) for k in ['first','second','top2','top3'])
            scenarios=c.get('scenario_groups',[])
            valid=valid and len(scenarios)>=2 and all(s.get('name') and s.get('reason') and len(set(s.get('numbers',[])))>=min(3,len(active)) and set(s['numbers'])<=set(known) for s in scenarios)
            if not valid:errors.append(('top3_coverage_review_missing',None,'4役割と主/別展開の馬券内候補を比較し、3頭捕捉の目的・非保証・採否理由を残す。'))
    # Compare the candidates just outside the mark boundary and credible rivals.
    omitted=[h for h in active if h['number'] not in actual]
    boundary={h['number'] for h in sorted(omitted,key=lambda h:(h.get('rank') is None,h.get('rank') or 999,h['number']))[:2]}
    credible={h['number'] for h in omitted if h.get('model_rank') in (1,2,3) or h.get('condition_return_candidate') or h.get('score_method')=='insufficient_evidence'}
    if policy==COVERAGE_POLICY:
        credible|={n for group in a.get('coverage_review',{}).get('candidate_groups',{}).values() if isinstance(group,list) for n in group if n in known and n not in actual}
    entries={e.get('number'):e for e in a.get('boundary_reviews',[]) if isinstance(e,dict)}
    all_refs={ref for h in active for ref in horse_evidence_refs(h)}
    for n in sorted(boundary|credible):
        e=entries.get(n,{});peers=set(e.get('compared_with',[]));refs=set(e.get('evidence_refs',[]))
        # Reference-only unbet races may have no independently selected marks.
        if not actual and not main_pool:continue
        own=horse_evidence_refs(known[n])
        valid=bool(peers and peers<=actual and e.get('reason') and refs<=all_refs)
        if own and not refs&own:valid=False
        if any(horse_evidence_refs(known[p]) and not refs&horse_evidence_refs(known[p]) for p in peers if p in known):valid=False
        if not valid:errors.append(('mark_boundary_comparison_missing',n,'印外の境界候補・指数上位・条件戻り・数値保留を、採用した印候補と根拠走付きで比較する。'))
    return errors
