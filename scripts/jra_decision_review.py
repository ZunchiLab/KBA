"""Require named counterevidence and the combinations omitted by a common core.

This checks an explicit review, not whether the prose or forecast is correct.
It never selects horses or changes wagers.
"""
from jra_role_indices import run_key

def evidence_book(horse):
    out={}
    for p in horse.get('past',[]):
        rid=p.get('run_id')
        if rid and p.get('finish') is not None:out[run_key(rid)]=p
    for p in horse.get('role_indices',{}).get('components',[]):out.setdefault(run_key(p['run_id']),p)
    return out

def risk_candidates(race):
    hs=[h for h in race['horses'] if h.get('status_at_snapshot')=='declared'];a=race.get('analysis',{})
    risk={h['number'] for h in hs if h.get('model_rank') in (1,2,3) or h.get('condition_return_candidate') or h.get('score_method')=='insufficient_evidence'}
    priced=sorted((h for h in hs if h.get('market',{}).get('win')),key=lambda h:h['market']['win']);risk|={h['number'] for h in priced[:4]}
    for role in ('first','second','top2','top3'):
        ranked=sorted((h for h in hs if h.get('role_indices',{}).get(role,{}).get('value') is not None),key=lambda h:-h['role_indices'][role]['value'])
        risk|={h['number'] for h in ranked[:4]}
    for group in a.get('mark_selection',{}).get('coverage_review',{}).get('candidate_groups',{}).values():risk.update(group)
    return risk

def audit_race(race):
    errors=[];hs={h['number']:h for h in race['horses'] if h.get('status_at_snapshot')=='declared'}
    plans=[p for p in race.get('bet_plans',[]) if p.get('selected_for_example')]
    if not plans:return errors
    usage=race.get('analysis',{}).get('role_index_usage_review',{})
    if usage.get('mode')!='auxiliary_only' or usage.get('benchmark_edge_unproven') is not True or not usage.get('independent_comparison_reason'):
        errors.append(('unvalidated_index_used_as_selection',None,'4指標の優位性は未確認。指標単独の機械選馬にせず、実績・条件・反証・市場評価を別に比較した記録を残す。'))
    adopted={n for p in plans for t in p['tickets'] for n in t['numbers']}
    review=race.get('analysis',{}).get('preflight_review',{});entries={e.get('number'):e for e in review.get('exclusions',[])}
    for n in sorted((risk_candidates(race)&set(hs))-adopted):
        entry=entries.get(n,{});own=entry.get('best_case',{});peer=entry.get('peer_case',{});pn=peer.get('number')
        own_id=run_key(own.get('run_id'));peer_id=run_key(peer.get('run_id'))
        refs={run_key(x) for x in entry.get('evidence_refs',[])}
        valid=own_id in evidence_book(hs[n]) and own.get('why_relevant') and pn in adopted and pn in hs
        valid=valid and peer_id in evidence_book(hs[pn]) and peer.get('why_prefer') and pn in entry.get('compared_with',[]) and {own_id,peer_id}<=refs
        if not valid:errors.append(('best_counterevidence_review_missing',n,'有力な除外馬の最良反証走と、採用相手の比較走を名指しし、今回条件で採用相手を優先する理由を保存する。最新凡走だけの定型文では完了にしない。'))
    dependencies={e.get('plan_id'):e for e in review.get('dependency_reviews',[])}
    all_refs={run_key(p) for h in hs.values() for p in h.get('evidence_refs',[])}|{key for h in hs.values() for key in evidence_book(h)}
    for p in plans:
        sets=[set(t['numbers']) for t in p['tickets']];core=set.intersection(*sets) if sets else set()
        if not core:continue
        e=dependencies.get(p.get('plan_id'),{});outside=set(e.get('without_core',[]));needed=3 if p['kind']=='trio' else 2
        enough=len(set(hs)-core)>=needed
        refs={run_key(x) for x in e.get('evidence_refs',[])}
        valid=core<=set(hs) and set(e.get('mandatory_numbers',[]))==core and e.get('retained_reason') and refs and refs<=all_refs
        valid=valid and all(refs&set(evidence_book(hs[n])) for n in core if n in hs)
        valid=valid and (len(outside)>=needed and outside<=set(hs)-core and all(refs&set(evidence_book(hs[n])) for n in outside) if enough else bool(e.get('no_feasible_without_core_reason')))
        if not valid:errors.append(('core_dependency_review_missing',None,'全点共通の必須馬と、その馬を含まない有力な二頭/三頭を比較し、現構成を残す理由と双方の根拠走を記録する。'))
    return errors
