"""Build reproducible, timestamped debut observations from saved JRA originals."""
from pathlib import Path
from hashlib import sha256
import json

def load_saved_observations(root, *, before_date=None):
    root=Path(root);latest={};observations=[];inputs=[]
    load=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
    for p in root.glob('predictions/report_*_jra_predictions_v*.json'):
        d=load(p);day=d['date_jst']
        if before_date and day>=before_date:continue
        if day not in latest or int(d['forecast_version'][1:])>int(latest[day][1]['forecast_version'][1:]):latest[day]=(p,d)
    for day,(p,d) in sorted(latest.items()):
        for v in d['venues']:
            rp=root/'data/results/jra'/day/d['forecast_version']/(v['venue_key']+'.json')
            if not rp.exists():continue
            res=load(rp)
            if res.get('forecast_ref',{}).get('file')!='predictions/'+p.name:raise ValueError('結果と固定予想の参照が不一致')
            inputs.extend([dict(path=str(q.relative_to(root)),sha256=sha256(q.read_bytes()).hexdigest()) for q in (p,rp)])
            for r in d['races']:
                if r['venue_key']!=v['venue_key'] or r['class_text']!='新馬':continue
                rr=next((a for a in res['races'] if a['race_no']==r['race_no']),None)
                if not rr or not rr.get('official_confirmed') or not rr.get('rows_complete'):continue
                field=sum(a['runner_status'] not in ('withdrawn','excluded') for a in rr['rows'])
                for h in r['horses']:
                    a=next(a for a in rr['rows'] if a['number']==h['number']);finish=a['finish']
                    if a['name']!=h['name']:raise ValueError('結果と出走馬の名前が不一致')
                    if not isinstance(finish,int) or isinstance(finish,bool):continue
                    observations.append(dict(observation_id=rr['race_uid']+'-n'+str(h['number']),date=day,race_uid=rr['race_uid'],number=h['number'],name=h['name'],horse_id=(h.get('source_horse_id') or {}).get('id') or h.get('horse_id'),surface=r['surface'],distance_m=r['distance_m'],field=field,finish=finish,sire=h.get('sire'),trainer=h.get('trainer'),jockey=h.get('jockey'),card_source=r['source'],result_source=rr['source'],official_confirmed=True,rows_complete=True))
    return observations,list({x['path']:x for x in inputs}.values())
