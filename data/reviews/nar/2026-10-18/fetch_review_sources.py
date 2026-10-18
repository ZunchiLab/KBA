from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request,urlopen
from datetime import datetime,timezone,timedelta
import json,sys,hashlib
ROOT=Path(__file__).resolve().parent;PROJECT=ROOT.parents[1];REPO=Path(r'C:\Users\furokei\Documents\Codex\KBA');OUT=PROJECT/'outputs/nar20261018_review';OUT.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(REPO/'scripts'));from update_nar_results import parse,Document
JST=timezone(timedelta(hours=9));fp=REPO/'predictions/report_20261018_nar_predictions_v1.json';f=json.loads(fp.read_text(encoding='utf-8-sig'));original=json.loads((PROJECT/'outputs/nar20261018/report_20261018_nar_predictions_v1.json').read_text(encoding='utf-8'));assert f['races']==original['races'],'frozen forecast content changed'
digest=hashlib.sha256(fp.read_text(encoding='utf-8-sig').replace('\r\n','\n').encode('utf-8')).hexdigest()
jobs=[]
for v in f['venues']:
 saved=json.loads((REPO/f"data/results/nar/2026-10-18/{v['venue_key']}.json").read_text(encoding='utf-8-sig'));assert saved['forecast_sha256']==digest and saved['complete']
 for old in saved['races']:
  race=next(r for r in f['races'] if r['venue_key']==v['venue_key'] and r['race']==old['race']);jobs.append((v,race,old))
def fetch(job):
 v,r,old=job;url=old['source']['url'];raw=urlopen(Request(url,headers={'User-Agent':'Mozilla/5.0 (post-race official review)'}),timeout=35).read();at=datetime.now(JST).isoformat(timespec='seconds');sha=hashlib.sha256(raw).hexdigest();rel=f"sources/{v['venue_key']}/r{r['race']}_{sha[:12]}.html";path=OUT/rel;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
 source=dict(url=url,retrieved_at=at,sha256=sha,saved_file=rel,provider='NAR');data=parse(raw,dict(f,venue=v['label']),r,source);assert data['status']=='confirmed';changes=[dict(number=x['number'],field=k,previous=next(y for y in old['rows'] if y['number']==x['number']).get(k),current=z) for x in data['rows'] for k,z in x.items() if next(y for y in old['rows'] if y['number']==x['number']).get(k)!=z];
 assert [(x['number'],x['finish']) for x in data['rows']]==[(x['number'],x['finish']) for x in old['rows']],'official finishing order revised';assert data['refunds']==old['refunds'],'official payouts revised';
 if changes:print(v['venue_key'],r['race'],'additional official fields',changes[:3]);
 data['updates_since_worker']=changes;data['previous_source']=old['source']
 text=Document(raw.decode('utf-8-sig')).root.text();data.update(race_uid=r['race_uid'],venue_key=v['venue_key'],venue=v['label'],race=r['race'],name=r['name'],start_at=r['start_at'],raw_text=text,corner_orders=[x.text() for x in Document(raw.decode('utf-8-sig')).root.nodes() if x.tag=='table' and any(w in x.text() for w in ['コーナー通過順','コーナー通過'])],corner_orders_missing='当日通過順は公式成績表に掲載がある場合のみ引用。映像未検証。展開の原因断定はしない。')
 return data
results=list(ThreadPoolExecutor(max_workers=3).map(fetch,jobs));payload=dict(schema_version='kba.nar-review-sources/1',date_jst='2026-10-18',reviewed_at=datetime.now(JST).isoformat(timespec='seconds'),forecast_sha256=digest,forecast_original_unchanged=True,results=results)
(OUT/'official_verification.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print('Fresh official verification:',len(results),'races',sum(len(r['rows']) for r in results),'horses; saved finishing orders/payouts unchanged; timing/3F enriched; forecast frozen unchanged; SHA',digest)
