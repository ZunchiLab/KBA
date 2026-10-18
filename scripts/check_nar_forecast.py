"""Check future NAR publication records; this does not predict outcomes."""
from argparse import ArgumentParser
from datetime import datetime
import json, math
from nar_display import ordinal_score

def audit(data):
    findings=[]
    if data.get('authority')!='nar' or data.get('document_type')!='prediction':
        return ['地方競馬の予想JSONが必要です。']
    if data.get('date_jst','')<'2026-10-19':
        return findings  # Preserve historical forecasts under their original contract.
    if data.get('presentation',{}).get('layout')!='compact-v1':
        findings.append('次回の地方HTMLはJRA共通のcompact-v1を指定してください。')
    for race in data.get('races',[]):
        uid=race['race_uid']
        if datetime.fromisoformat(data['fixed_at'])>=datetime.fromisoformat(race['start_at']):
            findings.append(uid+': 発走前に固定されていません。')
        for h in race['horses']:
            if h.get('status_at_snapshot') in ('withdrawn','excluded'):continue
            prefix=uid+'/'+str(h['number'])+': '
            score=h.get('score')
            if score is None:
                if h.get('score_method')!='not_computed' or not h.get('score_definition'):
                    findings.append(prefix+'指数未算出はscore:null、score_method:not_computedと理由を保存してください。')
                continue
            if ordinal_score(h):
                findings.append(prefix+'順位を等間隔へ変換した数値を能力指数として公開できません。')
            if not isinstance(score,(int,float)) or isinstance(score,bool) or not math.isfinite(score):
                findings.append(prefix+'数値指数が不正です。');continue
            evidence=h.get('score_evidence',{})
            if not h.get('score_method') or not h.get('score_definition'):
                findings.append(prefix+'指数の計算方法と定義が必要です。')
            if not evidence.get('formula') or not evidence.get('components'):
                findings.append(prefix+'順位とは別に、計算式と根拠走別の入力・寄与を保存してください。')
            for item in evidence.get('components',[]):
                if not item.get('run_id') or item['run_id'] not in h.get('evidence_refs',[]):
                    findings.append(prefix+'指数入力の根拠走が照合できません。')
                if not item.get('inputs') or not isinstance(item.get('contribution'),(int,float)):
                    findings.append(prefix+'指数入力値と計算への寄与が不足しています。')
    return findings

if __name__=='__main__':
    parser=ArgumentParser();parser.add_argument('json_file');parser.add_argument('--strict',action='store_true')
    args=parser.parse_args()
    with open(args.json_file,encoding='utf-8-sig') as handle:findings=audit(json.load(handle))
    for finding in findings:print(finding)
    print('地方公開前記録の指摘:',len(findings),'件。予測力・期待値の検証ではありません。')
    raise SystemExit(1 if args.strict and findings else 0)
