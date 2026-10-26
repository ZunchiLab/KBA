"""Pre-publication consistency and explicit-comparison gate, not a predictive model."""
from pathlib import Path
from argparse import ArgumentParser
from datetime import datetime
import json,math,re
from urllib.parse import urlparse
from jra_mark_policy import audit_race as audit_mark_selection

def audit(data,strict=False):
    findings=[]
    def add(code,race=None,number=None,message=''):
        findings.append(dict(code=code,severity='error' if strict else 'warning',race_uid=race,number=number,message=message))
    if data.get('authority')!='jra' or data.get('document_type')!='prediction':
        add('not_jra_prediction',message='JRAの予想JSONが必要。レビュー・結果を予想として公開しない。');return findings
    seen=set()
    for r in data.get('races',[]):
        uid=r['race_uid'];hs={h['number']:h for h in r['horses']};a=r.get('analysis',{});review=a.get('preflight_review',{})
        if uid in seen or len(hs)!=len(r['horses']):add('duplicate_identity',uid,message='レースIDまたは馬番の重複。')
        seen.add(uid)
        if (data.get('date_jst') or data['fixed_at'][:10]) >= '2026-10-26':
            for code,number,message in audit_mark_selection(r,data['fixed_at']):add(code,uid,number,message)
        if datetime.fromisoformat(data['fixed_at'])>=datetime.fromisoformat(r['start_at']):add('not_pre_race',uid,message='固定時刻が発走前ではない。')
        for h in hs.values():
            used=[p['run_id'] for p in h.get('evaluated_runs',[])]
            if len(used)!=len(set(used)):add('duplicate_scored_run',uid,h['number'],'同じ過去走を複数回集約している。')
            if any(not p.get('resolved_class') for p in h.get('evaluated_runs',[])):add('unclassified_run_scored',uid,h['number'],'級未確認の走を採点に使っている。')
        if hs and all(h.get('score_method')=='market_reference' for h in hs.values()):
            market=sorted((h for h in hs.values() if h.get('status_at_snapshot') not in ['withdrawn','excluded']),key=lambda h:(h['market']['win'] is None,h['market']['win'] or math.inf,h['number']))
            if any(h.get('rank')!=i+1 for i,h in enumerate(market)):add('market_reference_order_stale',uid,message='市場参考の順位が表示中の保存単勝順と違う。価格更新後に参考順位も確認する。')
        mains=[p for p in r.get('bet_plans',[]) if p.get('selected_for_example')]
        if not mains:continue
        if (data.get('date_jst') or data['fixed_at'][:10]) >= '2026-10-17':
            for n,h in hs.items():
                if h.get('status_at_snapshot') in ['withdrawn','excluded']:continue
                history=h.get('history_audit',{});source=history.get('source') or {}
                try:before=datetime.fromisoformat(source['retrieved_at'])<=datetime.fromisoformat(data['fixed_at'])
                except (KeyError,TypeError,ValueError):before=False
                valid=(history.get('status')=='parsed' and history.get('summary') and source.get('provider')=='JRA' and urlparse(source.get('url','')).hostname in ['jra.jp','www.jra.jp','jra.go.jp','www.jra.go.jp'] and re.fullmatch('[a-f0-9]{64}',source.get('raw_sha256','')) and before)
                if not valid:add('listed_history_scope_missing',uid,n,'本線レースの全出走予定馬について、発走前のJRA公式掲載戦歴の確認範囲・出典・取得時刻・原文SHAをhistory_auditへ保存。未解決なら本線を見送る。書式通過は初条件の文章の正しさを保証しない。')
        adopted={n for p in mains for t in p['tickets'] for n in t['numbers']}
        all_refs={ref for h in hs.values() for ref in h.get('evidence_refs',[])}
        def evidence(entry,number,compared):
            refs=set(entry.get('evidence_refs',[]));own=set(hs[number].get('evidence_refs',[]))
            return bool(compared and refs<=all_refs and refs&own and all(n in hs and refs&set(hs[n].get('evidence_refs',[])) for n in compared))
        if (data.get('date_jst') or data['fixed_at'][:10]) >= '2026-10-18':
            # Record substantial downgrades before results; this cannot validate
            # the semantic quality of the explanation or make a horse predictable.
            overrides={e.get('number'):e for e in review.get('rank_override_reviews',[])}
            for n,h in hs.items():
                if h.get('status_at_snapshot') in ['withdrawn','excluded']:continue
                if h.get('model_rank') not in [1,2,3] or (h.get('rank') is not None and h['rank']<5):continue
                e=overrides.get(n,{});compared=e.get('compared_with',[])
                peers=[k for k in compared if k!=n and k in hs and hs[k].get('rank') in [1,2,3,4]]
                if not (peers and e.get('reason') and not e['reason'].startswith('印・総合順位は今回条件と展開') and evidence(e,n,compared)):
                    add('large_rank_downgrade_comparison_missing',uid,n,'本線レースで指数上位3頭を総合5位以下・順位保留へ下げる場合、上位へ採用した馬との個別比較と双方の根拠走をpreflight_review.rank_override_reviewsへ保存する。定型的な理由では完了としない。')
            active=[h for h in hs.values() if h.get('status_at_snapshot') not in ['withdrawn','excluded']]
            priced=sorted((h for h in active if h.get('market',{}).get('win') is not None),key=lambda h:(h['market']['win'],h['number']))
            credible={h['number'] for h in priced[:4]} | {h['number'] for h in active if h.get('model_rank') in [1,2,3] or h.get('condition_return_candidate')}
            for p in mains:
                if p['kind']!='wide':continue
                groups=p.get('groups') or [t['numbers'] for t in p['tickets']]
                common=set.intersection(*(set(g) for g in groups)) if groups else set()
                declared=a.get('trio',[])
                axis={declared[0]} if declared and declared[0] in common else common if len(common)==1 else set()
                pool={n for t in p['tickets'] for n in t['numbers']};counterparts=pool-axis
                plan_review=next((e for e in a.get('formation_review',{}).get('plans',[]) if e.get('linked_plan_id')==p.get('plan_id')),{})
                entries={e.get('number'):e for e in plan_review.get('counterpart_exclusions',[])}
                for n in sorted(credible-pool):
                    e=entries.get(n,{});compared=e.get('compared_with',[])
                    if not (set(compared)<=pool and set(compared)&counterparts and e.get('reason') and evidence(e,n,compared)):
                        add('wide_counterpart_slot_comparison_missing',uid,n,'本線ワイドの相手外へ朝単勝上位4頭・指数上位3頭・条件戻り候補を置く場合、軸だけでなく採用相手との直接比較と双方の根拠走をformation_review.plans[].counterpart_exclusionsへ保存する。')
        for p in mains:
            if p['kind']!='win':continue
            for t in p['tickets']:
                n=t['numbers'][0];e=review.get('single_win_edge',{});rivals=set(a.get('win_candidates',[])+a.get('place_candidates',[]))-{n};compared=e.get('rival_numbers',[])
                if e.get('number')!=n or not rivals<=set(compared) or not e.get('why_win_not_only_place') or not evidence(e,n,compared):
                    add('single_win_edge_missing',uid,n,'圏内の安定性とは別に、各有力相手より勝ち切る理由と双方の根拠走が必要。説明できなければ単勝本線を見送る。')
        # Prospective only: an omitted counterpart competes with another counterpart,
        # not merely with the strongest axis. Preserve previously fixed forecasts.
        if (data.get('date_jst') or data['fixed_at'][:10]) >= '2026-10-12':
            market=sorted(hs.values(),key=lambda h:(h['market']['win'] is None,h['market']['win'] or math.inf,h['number']))
            priced=[h for h in market if h['market']['win'] is not None]
            credible={h['number'] for h in priced[:4]} | {n for n,h in hs.items() if h.get('condition_return_candidate')}
            formation=a.get('formation_review',{})
            for p in mains:
                if p['kind'] not in ['quinella','trio']:continue
                pool={n for t in p['tickets'] for n in t['numbers']}
                axes=set((p.get('groups') or [[]])[0]);counterparts=pool-axes
                plan_review=next((e for e in formation.get('plans',[]) if e.get('linked_plan_id')==p.get('plan_id')), {})
                entries={e.get('number'):e for e in plan_review.get('counterpart_exclusions',[])}
                for n in sorted(credible-pool):
                    e=entries.get(n,{});compared=e.get('compared_with',[])
                    if not (set(compared)<=pool and set(compared)&counterparts and e.get('reason') and evidence(e,n,compared)):
                        add('counterpart_slot_comparison_missing',uid,n,'保存単勝上位4頭・条件戻り候補を本線の馬連／三連複候補群から外す時は、枠を争う採用相手（軸以外）との比較と双方の根拠走をformation_review.plans[].counterpart_exclusionsへ保存する。')
        # Compare all uncertain runners and credible omitted opponents, not just today's eventual winners.
        exclusions={x['number']:x for x in review.get('exclusions',[]) if 'number' in x}
        for n,h in hs.items():
            recent=next((p for p in h.get('past',[]) if p.get('finish') is not None),None)
            near_recent=bool(recent and recent['finish']<=3 and recent.get('class_adjustment')==0 and abs((recent.get('distance') or 0)-r['distance_m'])<=200)
            uncertainty=h.get('score_method')=='insufficient_evidence'
            credible=uncertainty or n in a.get('win_candidates',[]) or n in a.get('place_candidates',[]) or h.get('model_rank') in [1,2,3] or near_recent or h.get('condition_return_candidate')
            if n in adopted or not credible:continue
            e=exclusions.get(n,{});compared=e.get('compared_with',[])
            valid=bool(set(compared)&adopted and e.get('reason') and evidence(e,n,compared))
            if not valid:add('opponent_comparison_missing',uid,n,'比較不足・有力候補・直近好走の除外は、採用馬を名指しした同基準の比較と双方の根拠走を残す。')
            if uncertainty and not e.get('unknown_is_not_inferior_reason'):
                add('uncertainty_not_resolved',uid,n,'数値保留を最下位・不適性へ置き換えない。未知のまま採用馬を優先できる理由が必要。未解決ならレース本線を見送る。')
        scenarios={x.get('scenario'):x for x in review.get('scenario_checks',[])}
        for name in ['main','alternate']:
            e=scenarios.get(name,{})
            if e.get('response') not in ['keep','skip','replace'] or not e.get('reason') or not e.get('evidence_refs') or not set(e['evidence_refs'])<=all_refs:
                add('scenario_ticket_audit_missing',uid,message=name+'展開で軸・相手と買い目を維持する／見送る／差し替える根拠を記録する。')
        claims=review.get('fact_checks',[])
        if not claims:add('source_claim_checks_missing',uid,message='本文の級・距離・着順を根拠走の値へ照合する記録が必要。')
        for c in claims:
            h=hs.get(c.get('number'),{});past=next((p for p in h.get('past',[]) if p.get('run_id')==c.get('run_id')),None)
            if not past or c.get('field') not in past or past[c['field']]!=c.get('expected'):
                add('source_claim_mismatch',uid,c.get('number'),'根拠走の原文・構造値と記載値が一致しない。')
    total=sum(t['example_stake_yen'] for r in data.get('races',[]) for p in r.get('bet_plans',[]) if p.get('selected_for_example') for t in p['tickets'])
    if total!=data.get('budget',{}).get('selected_main_yen'):add('budget_mismatch',message='本線の全点費用と掲載合計が違う。')
    return findings

if __name__=='__main__':
    ap=ArgumentParser();ap.add_argument('forecast');ap.add_argument('--strict',action='store_true');ap.add_argument('--output');args=ap.parse_args()
    data=json.loads(Path(args.forecast).read_text(encoding='utf-8-sig'));findings=audit(data,args.strict)
    result=dict(schema_version='kba.jra-preflight/1',forecast=args.forecast,strict=args.strict,passed=not findings,scope='形式・整合性と明示的比較の記録を確認。自由文の全事実・能力・期待値・未来の的中は検証しない。',findings=findings)
    text=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
    if args.output:Path(args.output).write_text(text,encoding='utf-8',newline='\n')
    print(text)
    if args.strict and findings:raise SystemExit(1)
