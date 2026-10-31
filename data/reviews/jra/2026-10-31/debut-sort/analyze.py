from pathlib import Path
from datetime import datetime,timezone,timedelta
from hashlib import sha256
from statistics import mean,median
import json,sys
ROOT=Path(__file__).resolve().parents[2];KBA=Path('C:/Users/furokei/Documents/Codex/KBA');OUT=ROOT/'outputs/20261031_debut_sort'
sys.path.insert(0,str(KBA/'scripts'))
from jra_role_indices import apply_indices,ROLES
from jra_debut_indices import VERSION
from jra_debut_corpus import load_saved_observations
from jra_rank_coverage import ordered_horses,needed_prefix
NOW=datetime.now(timezone(timedelta(hours=9))).isoformat(timespec='seconds')
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
latest={}
for p in KBA.glob('predictions/report_*_jra_predictions_v*.json'):
 d=load(p);day=d['date_jst']
 if day not in latest or int(d['forecast_version'][1:])>int(latest[day][1]['forecast_version'][1:]):latest[day]=(p,d)
corpus=[];inputs=[];results={}
for day,(p,d) in sorted(latest.items()):
 inputs.append(dict(path=str(p.relative_to(KBA)),sha256=sha256(p.read_bytes()).hexdigest(),fixed_at=d['fixed_at']))
 for v in d['venues']:
  rp=KBA/'data/results/jra'/day/d['forecast_version']/(v['venue_key']+'.json');res=load(rp)
  inputs.append(dict(path=str(rp.relative_to(KBA)),sha256=sha256(rp.read_bytes()).hexdigest()))
  for rr in res['races']:results[(day,v['venue_key'],rr['race_no'])]=rr
 for r in d['races']:
  if r['class_text']!='新馬':continue
  rr=results[(day,r['venue_key'],r['race_no'])];assert rr['official_confirmed'] and rr['rows_complete']
  field=sum(h['runner_status'] not in ('withdrawn','excluded') for h in rr['rows'])
  for h in r['horses']:
   a=next(a for a in rr['rows'] if a['number']==h['number']);finish=a['finish']
   assert a['name']==h['name']
   if not isinstance(finish,int) or isinstance(finish,bool):continue
   corpus.append(dict(observation_id=rr['race_uid']+'-n'+str(h['number']),date=day,race_uid=rr['race_uid'],number=h['number'],name=h['name'],horse_id=(h.get('source_horse_id') or {}).get('id') or h.get('horse_id'),surface=r['surface'],distance_m=r['distance_m'],field=field,finish=finish,sire=h.get('sire'),trainer=h.get('trainer'),jockey=h.get('jockey'),card_source=r['source'],result_source=rr['source'],official_confirmed=True,rows_complete=True))
shared_corpus,corpus_inputs=load_saved_observations(KBA)
assert {x['observation_id']:x for x in shared_corpus}=={x['observation_id']:x for x in corpus}
corpus=shared_corpus
save(OUT/'新馬関連実績コーパス.json',dict(version=VERSION,built_at=NOW,phase='post_event_dataset',scope='保存8開催日の新馬戦のみ。全国通年成績ではない。使用時に対象日より前・入力確認時点以前へ限定。',inputs=corpus_inputs,observations=corpus))
METHODS=dict(rank='朝の総合印順',score='朝の旧総合指数',first='1着指標v2',second='2着ちょうど指標v2',top2='連対指標v2',top3='3着内指標v2',market='朝の単勝人気順',number='馬番順（対照）')
def order(hs,method):
 def value(h):return h.get('market',{}).get('win') if method=='market' else h['role_indices'][method]['value'] if method in ROLES else h.get(method)
 def key(h):
  v=value(h);return (v is None,v if method in ('rank','market','number') else -v if v is not None else 0,h.get('rank') or 999,h['number'])
 available_count=sum(value(h) is not None for h in hs)
 if method in ROLES and all(h['role_indices']['method']=='debut_cohort_reference' for h in hs):
  available_count=sum(bool(h['role_indices']['matched_starters']) for h in hs)
 ordered,available=ordered_horses(hs,method)
 assert [h['number'] for h in ordered]==[h['number'] for h in sorted(hs,key=key)] and available==available_count
 return ordered,available
rows=[];today=None
for day,(path,d) in sorted(latest.items()):
 hp=ROOT/'work'/day.replace('-','')/'histories.json';hist=load(hp)['horses'] if hp.exists() else []
 enriched=[]
 for r in d['races']:
  histories={h['number']:h for h in hist if h['key']==r['key'] and h.get('status')=='parsed' and h['source']['retrieved_at']<=d['fixed_at']}
  fr=apply_indices(r,as_of=d['fixed_at'],computed_at=NOW,history_by_number=histories,debut_observations=corpus);enriched.append(fr)
  actual=results[(day,r['venue_key'],r['race_no'])];assert actual['official_confirmed'] and actual['rows_complete']
  finishes={h['number']:h['finish'] for h in actual['rows']};placed={n for n,f in finishes.items() if isinstance(f,int) and not isinstance(f,bool) and f<=3}
  assert len(placed)>=3
  hs=[h for h in fr['horses'] if h['status_at_snapshot'] not in ('withdrawn','excluded')]
  methods={}
  for method in METHODS:
   ordered,numeric=order(hs,method);numbers=[h['number'] for h in ordered];positions={n:i+1 for i,n in enumerate(numbers)}
   needed=max(positions[n] for n in placed)
   assert needed==needed_prefix(numbers,actual['rows'])
   methods[method]=dict(order=numbers,numeric_count=numeric,available=bool(numeric),placed_positions=[dict(number=n,finish=finishes[n],position=positions[n]) for n in sorted(placed,key=lambda n:(finishes[n],n))],needed_prefix=needed,all_inside={str(k):placed<=set(numbers[:k]) for k in [3,4,5,6,7]},captured={str(k):len(placed&set(numbers[:k])) for k in [3,4,5,6,7]})
  best=min(x['needed_prefix'] for k,x in methods.items() if k!='number' and x['available'])
  rows.append(dict(date=day,key=r['key'],venue=r['venue'],race_no=r['race_no'],class_text=r['class_text'],surface=r['surface'],field=len(hs),actual_placed=[dict(number=n,name=next(h['name'] for h in hs if h['number']==n),finish=finishes[n]) for n in sorted(placed,key=lambda n:(finishes[n],n))],methods=methods,hindsight_best_prefix=best,hindsight_best_methods=[k for k,x in methods.items() if k!='number' and x['available'] and x['needed_prefix']==best]))
 if day=='2026-10-31':today=dict(d,races=enriched)
 print(day,'processed',len(d['races']),flush=True)
def summary(rs):
 return {m:dict(label=METHODS[m],races=len(rs),available=sum(r['methods'][m]['available'] for r in rs),all_inside={str(k):sum(r['methods'][m]['available'] and r['methods'][m]['all_inside'][str(k)] for r in rs) for k in [3,4,5,6,7]},captured={str(k):sum(r['methods'][m]['captured'][str(k)] for r in rs if r['methods'][m]['available']) for k in [3,4,5,6,7]},placed_total=sum(len(r['actual_placed']) for r in rs),mean_prefix=round(mean(r['methods'][m]['needed_prefix'] for r in rs if r['methods'][m]['available']),2) if any(r['methods'][m]['available'] for r in rs) else None,median_prefix=median(r['methods'][m]['needed_prefix'] for r in rs if r['methods'][m]['available']) if any(r['methods'][m]['available'] for r in rs) else None) for m in METHODS}
flat=lambda r:r['class_text']!='新馬' and r['surface'] not in ('hurdle','障')
report=dict(document_type='method_review',phase='post_event_diagnostic',computed_at=NOW,current_date='2026-10-31',retrospective_known_outcomes=True,coefficients_fitted_to_current_results=False,methods=METHODS,inputs=inputs,scopes=dict(today_all=summary([r for r in rows if r['date']=='2026-10-31']),today_flat=summary([r for r in rows if r['date']=='2026-10-31' and flat(r)]),eight_days_flat=summary([r for r in rows if flat(r)]),today_debut=summary([r for r in rows if r['date']=='2026-10-31' and r['class_text']=='新馬']),eight_days_debut=summary([r for r in rows if r['class_text']=='新馬'])),rows=rows,limitations=['結果既知の事後診断。新方式の事前成績や未知日の改善実証ではない。','各日の発走前保存資料とそれ以前に取得済みの他レース結果だけを入力。新馬は対象日より前の新馬成績のみ。','同点は朝総合順、次に馬番。馬番順自体は対照。欠損は末尾、取消除外は対象外。全指標欠損なら利用不可として成功数に加えない。','朝人気は保存単勝オッズの小さい順。最終人気は使わない。','全包含は公式3着以内の全頭。同着で4頭なら全4頭を対象にし、上位3頭で全包含と数えない。','上位5頭以内に3頭が含まれても、掲載馬券の的中とは限らない。BOX購入や予算増額を推奨する数値ではない。','新馬参考は父・厩舎・騎手の限定的な関連実績。本人の調教・実戦能力・母系の網羅評価ではなく、市場値は使わない。'])
save(OUT/'並び順の全比較.json',report);save(OUT/'新馬追加見本データ.json',today)
common=[r for r in rows if r['class_text']=='新馬' and all(r['methods'][m]['available'] for m in ROLES)]
report['scopes']['eight_days_debut_common']=summary(common)
save(OUT/'並び順の全比較.json',report)
stats=[h['role_indices'] for r in today['races'] if r['class_text']=='新馬' for h in r['horses']]
print(json.dumps(dict(scopes=report['scopes'],debut=dict(horses=len(stats),with_matches=sum(bool(x['components']) for x in stats),range=[min(d[k]['value'] for d in stats for k in ROLES),max(d[k]['value'] for d in stats for k in ROLES)],corpus=len(corpus))),ensure_ascii=False))
