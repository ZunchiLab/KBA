"""Bounded JRA results collection. Discover every CNAME from official menus."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
from hashlib import sha256
from argparse import ArgumentParser
from contextlib import contextmanager
import json,re,urllib.request,urllib.parse,subprocess,time,os,sys,tempfile
from bs4 import BeautifulSoup
from render_jra_prediction import render_day_snapshot
ROOT=Path(__file__).resolve().parents[1];JST=timezone(timedelta(hours=9))
KINDS={'win':'win','place':'place','wide':'wide','umaren':'quinella','umatan':'exacta','trio':'trio','tierce':'trifecta','trifecta':'trifecta','wakuren':'bracket_quinella'}
def now():return datetime.now(JST).isoformat(timespec='seconds')
def atomic(path,d):
    path.parent.mkdir(parents=True,exist_ok=True);p=path.with_name(path.name+'.tmp');p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n');p.replace(path)
def raw_fetch(endpoint,token,date,venue):
    url='https://jra.jp/JRADB/'+endpoint;body=urllib.parse.urlencode({'cname':token}).encode()
    b=urllib.request.urlopen(urllib.request.Request(url,data=body,headers={'User-Agent':'Mozilla/5.0'}),timeout=20).read();s=b.decode('cp932')
    if 'パラメータエラー' in s:raise ValueError('Official parameter error')
    digest=sha256(b).hexdigest();p=ROOT/'data/results/sources/jra'/date/venue/(digest+'.raw.html');p.parent.mkdir(parents=True,exist_ok=True)
    if not p.exists():p.write_bytes(b)
    source=dict(provider='JRA',url=url,method='POST',request_fields={'cname':token},retrieved_at=now(),raw_sha256=digest,raw_file=p.relative_to(ROOT).as_posix(),encoding='cp932')
    return s,source
def tokens(s):
    out=[];soup=BeautifulSoup(s,'html.parser')
    for a in soup.select('a'):
        m=re.search(r"doAction\('/JRADB/accessS.html',\s*'([^']+)'",a.get('onclick',''))
        if m:out.append(m[1])
        href=a.get('href','');m=re.search(r'accessS.html\?CNAME=([^&]+)',href)
        if m:out.append(urllib.parse.unquote(m[1]))
    return list(dict.fromkeys(out))
def parse(s,forecast,source):
    soup=BeautifulSoup(s,'html.parser');hd=soup.select_one('.race_header')
    wanted=datetime.fromisoformat(forecast['start_at']).strftime('%Y年%-m月%-d日') if os.name!='nt' else f'{forecast["start_at"][:4]}年{int(forecast["start_at"][5:7])}月{int(forecast["start_at"][8:10])}日'
    if not hd or wanted not in hd.get_text(' ',strip=True):raise ValueError('Result date mismatch')
    number=hd.select_one('.race_number img');m=re.search(r'(\d+)レース',number.get('alt','') if number else '')
    if not m or int(m[1])!=forecast['race_no']:raise ValueError('Result race number mismatch')
    venue={'tokyo':'東京','kyoto':'京都'}.get(forecast.get('venue_key'))
    if venue and venue not in hd.get_text():raise ValueError('Result venue mismatch')
    title=hd.select_one('.race_name')
    if not title or re.sub(r'\s+','',title.get_text())!=re.sub(r'\s+','',forecast['name']):raise ValueError('Result race title mismatch')
    rows=[]
    for tr in soup.select('table tr'):
        num=tr.select_one('td.num');place=tr.select_one('td.place');horse=tr.select_one('td.horse')
        if not num or not place or not horse:continue
        nr=int(num.get_text(strip=True));rank=place.get_text(strip=True);name=re.sub(r'\s+','',horse.get_text())
        def txt(cls):x=tr.select_one('td.'+cls);return x.get_text(' ',strip=True) if x else None
        state='finished' if rank.isdigit() else 'withdrawn' if '取消' in rank else 'excluded' if '除外' in rank else 'did_not_finish' if '中止' in rank else 'disqualified' if '失格' in rank else 'unknown'
        rows.append(dict(number=nr,name=name,finish=int(rank) if rank.isdigit() else None,runner_status=state,official_status_text=rank,time=txt('time'),margin=txt('margin'),last_3f=txt('f_time'),final_popularity=txt('pop'),final_win_odds=None))
    known={h['number']:re.sub(r'\s+','',h['name']) for h in forecast['horses']};seen=set()
    for row in rows:
        if row['number'] not in known or row['name']!=known[row['number']] or row['number'] in seen:raise ValueError('Result horse identity mismatch')
        seen.add(row['number'])
    payouts=[];refund=soup.select_one('.refund_unit')
    if refund:
        for li in refund.select('li'):
            kind=next((KINDS[c] for c in li.get('class',[]) if c in KINDS),None)
            if not kind:continue
            for line in li.select('.line'):
                num=line.select_one('.num');yen=line.select_one('.yen')
                if not num or not yen:continue
                amount=re.sub(r'\D','',yen.get_text());numbers=[int(x) for x in re.findall(r'\d+',num.get_text())]
                if not amount or not numbers:continue
                if kind not in ['exacta','trifecta']:numbers.sort()
                payouts.append(dict(kind=kind,number_type='bracket' if kind=='bracket_quinella' else 'horse',numbers=numbers,yen_per_100=int(amount),popularity=None))
    complete=seen==set(known);required={'win','place','wide','quinella','trio','trifecta'};paid=required<={x['kind'] for x in payouts}
    return dict(race_uid=forecast['race_uid'],race_no=forecast['race_no'],start_at=forecast['start_at'],status='confirmed' if complete and paid else 'partial' if rows else 'pending',official_confirmed=bool(complete and paid),source=source,source_checked_at=source['retrieved_at'],rows_complete=complete,rows=rows,payouts=payouts,payouts_status={k:'confirmed' if complete and paid else 'partial' for k in required},refunds=[],refund_status='unconfirmed' if any(r['runner_status'] in ['withdrawn','excluded'] for r in rows) else 'no_runner_refund_indication',refresh_error=None)
def initial(r):return dict(race_uid=r['race_uid'],race_no=r['race_no'],start_at=r['start_at'],status='not_started',official_confirmed=False,source=None,source_checked_at=None,rows_complete=False,rows=[],payouts=[],payouts_status={},refunds=[],refund_status='unconfirmed',refresh_error=None)
def update(config,recheck=False):
    forecast=ROOT/config['forecast'];text=forecast.read_text(encoding='utf-8-sig').replace('\r\n','\n');d=json.loads(text);digest=sha256(text.encode()).hexdigest();assert d['authority']=='jra' and d['date_jst']==config['date']
    stamp=now();datasets={};changed=[];wanted=[]
    for v in d['venues']:
        key=v['venue_key'];rs=[r for r in d['races'] if r['venue_key']==key];path=ROOT/'data/results/jra'/d['date_jst']/d['forecast_version']/(key+'.json')
        data=json.loads(path.read_text(encoding='utf-8')) if path.exists() else dict(schema_version='kba.results/1',authority='jra',date_jst=d['date_jst'],venue_key=key,forecast_ref=dict(file=config['forecast'],version=d['forecast_version'],sha256=digest,hash_method='utf8-no-bom-lf-sha256'),updated_at=stamp,last_poll_at=None,published_at=None,races=[initial(r) for r in rs])
        if data['forecast_ref']['sha256']!=digest:raise ValueError('Frozen forecast changed')
        for rr in data['races']:
            if rr['status']=='not_started' and datetime.fromisoformat(rr['start_at'])<=datetime.now(JST):rr['status']='pending'
            if datetime.fromisoformat(rr['start_at'])<=datetime.now(JST) and (recheck or rr['status'] not in ['confirmed','cancelled']):wanted.append((key,rr['race_no']))
        datasets[key]=(path,data)
    menu=None;menu_error=None
    if wanted:
        try:menu,_=raw_fetch('accessS.html',config['result_menu_cname'],d['date_jst'],'menu')
        except Exception as e:menu_error=str(e)
    urls={}
    if menu:
        date=d['date_jst'].replace('-','')
        for token in tokens(menu):
            m=re.search(r'^pw01srl\d{2}(05|08)\d{8}'+date+r'/',token)
            if not m:continue
            key='tokyo' if m[1]=='05' else 'kyoto'
            if not any(k==key for k,n in wanted):continue
            try:
                page,_=raw_fetch('accessS.html',token,d['date_jst'],key+'_menu')
                for t in tokens(page):
                    mm=re.search(r'^pw01sde\d{2}(05|08)\d{8}(\d{2})'+date+r'/',t)
                    if mm:urls[('tokyo' if mm[1]=='05' else 'kyoto',int(mm[2]))]=t
            except Exception as e:menu_error=str(e)
    for key,no in wanted:
        path,data=datasets[key];i=next(i for i,r in enumerate(data['races']) if r['race_no']==no);old=data['races'][i]
        if (key,no) not in urls:
            if menu_error:old['refresh_error']=dict(at=stamp,reason=menu_error)
            continue
        try:
            s,src=raw_fetch('accessS.html',urls[key,no],d['date_jst'],key);r=next(r for r in d['races'] if r['venue_key']==key and r['race_no']==no);fresh=parse(s,r,src)
            if old['official_confirmed'] and not fresh['official_confirmed']:old['refresh_error']=dict(at=stamp,reason='New response incomplete; confirmed result retained')
            else:data['races'][i]=fresh
        except Exception as e:old['refresh_error']=dict(at=stamp,reason=str(e))
    for key,(path,data) in datasets.items():
        before=json.loads(path.read_text(encoding='utf-8')) if path.exists() else None
        data['last_poll_at']=stamp
        if not before or before['races']!=data['races']:data['updated_at']=stamp;atomic(path,data);changed.append(path.relative_to(ROOT).as_posix())
    if changed:render_day_snapshot(config['forecast'])
    return all(all(r['status'] in ['confirmed','cancelled'] for r in data['races']) for _,data in datasets.values()),changed
def git(*args,check=True):
    p=subprocess.run(['git',*args],cwd=ROOT,timeout=45,text=True,capture_output=True)
    if check and p.returncode:raise RuntimeError('git '+args[0]+': '+p.stderr.strip()[:400])
    return p
def publish(config):
    allowed=['data/results/jra/'+config['date'],'data/results/sources/jra/'+config['date'],str(Path(config['forecast']).with_suffix('.html')).replace('\\','/')]
    for name in ['rebase-merge','rebase-apply','MERGE_HEAD']:
        value=git('rev-parse','--git-path',name).stdout.strip()
        if (ROOT/value).exists():raise RuntimeError('Existing merge/rebase; publication held')
    staged=git('diff','--cached','--name-only').stdout.splitlines()
    if any(not any(p==a or p.startswith(a+'/') for a in allowed) for p in staged):raise RuntimeError('Unrelated staged changes; publication held')
    existing=[p for p in allowed if (ROOT/p).exists()]
    git('add','--',*existing)
    if git('diff','--cached','--quiet',check=False).returncode==1:git('commit','-m','Update official JRA results '+config['date'])
    # Retry already queued commits as well as fresh differences.
    for i in range(3):
        try:git('pull','--rebase','origin','main');git('push','origin','HEAD:main');return
        except Exception:
            # Abort only the rebase attempted here, preserving our queued commit.
            if any((ROOT/git('rev-parse','--git-path',n).stdout.strip()).exists() for n in ['rebase-merge','rebase-apply']):git('rebase','--abort')
            if i==2:raise
            time.sleep(3+i*5)
def run(args):
    config=json.loads((ROOT/args.config).read_text(encoding='utf-8'));state=ROOT/config['state_file'];until=datetime.fromisoformat(config['active_until'])
    while datetime.now(JST)<until:
        try:
            complete,changed=update(config,args.recheck)
            if args.publish:publish(config)
            atomic(state,dict(at=now(),state='complete' if complete else 'waiting_or_collecting',pid=os.getpid(),last_cycle_ok=True,changed=changed,stop_at=config['active_until']))
            print(now(),'complete',complete,'changed',len(changed),flush=True)
            if complete or args.once:return
            time.sleep(min(120,max(1,(until-datetime.now(JST)).total_seconds())))
        except Exception as e:
            atomic(state,dict(at=now(),state='retrying',pid=os.getpid(),error=str(e),stop_at=config['active_until']));print(now(),str(e),flush=True)
            if args.once:raise
            time.sleep(15)
    atomic(state,dict(at=now(),state='stopped_at_deadline',pid=os.getpid(),stop_at=config['active_until']))
@contextmanager
def lock():
    # Local collection only. Byte-range lock is automatically released on process exit.
    p=ROOT/'.git/kba-jra-results.lock';f=p.open('a+b');f.seek(0);f.write(b'1');f.flush();f.seek(0)
    try:
        if os.name=='nt':
            import msvcrt;msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl;fcntl.flock(f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        yield
    finally:f.close()
if __name__=='__main__':
    ap=ArgumentParser();ap.add_argument('--config',default='data/results/jra-targets.json');ap.add_argument('--once',action='store_true');ap.add_argument('--publish',action='store_true');ap.add_argument('--recheck',action='store_true');args=ap.parse_args()
    with lock():run(args)
