"""Pre-publication consistency and explicit-comparison gate, not a predictive model."""
from pathlib import Path
from argparse import ArgumentParser
from datetime import datetime
import json,math

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
        if datetime.fromisoformat(data['fixed_at'])>=datetime.fromisoformat(r['start_at']):add('not_pre_race',uid,message='固定時刻が発走前ではない。')
        for h in hs.values():
            used=[p['run_id'] for p in h.get('evaluated_runs',[])]
            if len(used)!=len(set(used)):add('duplicate_scored_run',uid,h['number'],'同じ過去走を複数回集約している。')
            if any(not p.get('resolved_class') for p in h.get('evaluated_runs',[])):add('unclassified_run_scored',uid,h['number'],'級未確認の走を採点に使っている。')
        if hs and all(h.get('score_method')=='market_reference' for h in hs.values()):
            market=sorted(hs.values(),key=lambda h:(h['market']['win'] is None,h['market']['win'] or math.inf,h['number']))
            if any(h.get('rank')!=i+1 for i,h in enumerate(market)):add('market_reference_order_stale',uid,message='市場参考の順位が表示中の保存単勝順と違う。価格更新後に参考順位も確認する。')
        mains=[p for p in r.get('bet_plans',[]) if p.get('selected_for_example')]
        if not mains:continue
        adopted={n for p in mains for t in p['tickets'] for n in t['numbers']}
        all_refs={ref for h in hs.values() for ref in h.get('evidence_refs',[])}
        def evidence(entry,number,compared):
            refs=set(entry.get('evidence_refs',[]));own=set(hs[number].get('evidence_refs',[]))
            return bool(compared and refs<=all_refs and refs&own and all(n in hs and refs&set(hs[n].get('evidence_refs',[])) for n in compared))
        for p in mains:
            if p['kind']!='win':continue
            for t in p['tickets']:
                n=t['numbers'][0];e=review.get('single_win_edge',{});rivals=set(a.get('win_candidates',[])+a.get('place_candidates',[]))-{n};compared=e.get('rival_numbers',[])
                if e.get('number')!=n or not rivals<=set(compared) or not e.get('why_win_not_only_place') or not evidence(e,n,compared):
                    add('single_win_edge_missing',uid,n,'圏内の安定性とは別に、各有力相手より勝ち切る理由と双方の根拠走が必要。説明できなければ単勝本線を見送る。')
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
