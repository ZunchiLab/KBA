from pathlib import Path
from datetime import datetime, timezone, timedelta
import json, sys, re, shutil, hashlib, unicodedata
from opinions import RACES, BETS, POPULAR_COMPARE, GROUPS, EXCLUDED, quin, trio
ROOT=Path(__file__).resolve().parent
PROJECT=ROOT.parents[1]
REPO=Path(r'C:\Users\furokei\Documents\Codex\KBA')
SHARED=PROJECT.parent.parent/'2026-09-26'/'referenced-chatgpt-conversation-this-is-an'
sys.path.insert(0,str(REPO/'scripts'))
from render_day_prediction import render
JST=timezone(timedelta(hours=9)); DATE='2026-10-18'; VERSION='v1'; NAME='report_20261018_nar_predictions_v1'
NOW=datetime.now(JST); FIXED=NOW.isoformat(timespec='seconds')
DEFINITION='同一レース内の主観的な総合順位を88点から2点刻みで表示。点差は能力差・確率ではない。未学習・未校正。'
AUDIT=[]
EXTRA=[dict(x['source'],provider='NAR',venue_key=x['venue'],number=x['number'],scope='公式履歴の2026年同場・同距離。未確認の以前の走を不存在にしない。') for x in json.loads((ROOT/'history.json').read_text(encoding='utf-8'))]
def source(s,v):
    return dict(s,provider='NAR',raw_sha256=s['sha256'],raw_file=f'sources/{v}/'+s['saved_file'],encoding='utf-8')

def comparison(h,r,o,plans):
    actual=[p for p in h['past'] if p['rank'] not in ('取消','除外','取止')]
    last=actual[0] if actual else None
    dates=re.search(r'(\d{2})\.(\d{2})\.(\d{2})',last['overview']) if last else None
    date=datetime(2000+int(dates[1]),int(dates[2]),int(dates[3]),tzinfo=JST) if dates else None
    interval=(NOW.date()-date.date()).days if date else None
    recency=(f'直近の実出走 {date.date().isoformat()}／{interval}日前。' if date else '実出走日不明。')+'調教・パドック・当日状態は未確認。'
    if last and not last['rank'].isdigit():recency+='最終出走は'+last['rank']+'で、通常の完走実績と区別。'
    local=re.search(r'場\s*(.*?)\s*距\s*(.*?)\s+(?:\d+:|－)',h['record'])
    suitability=f'公式記載の場・距離別成績：場 {local[1]}／距 {local[2]}。' if local else '公式記載成績：'+h['record']
    suitability+='未経験・圏外は不適性の証明とは区別する。'
    position=' ／ '.join(p['overview']+'：'+(p['time_corners'] or '通過順なし') for p in actual[:2]) or '記載なし'
    num=h['number']; main=[t for p in plans if p['role']=='main' for t in p['tickets'] if num in t['numbers']]
    alternative=[(t['numbers'].index(num)+1) for p in plans if p['role']=='alternative' for t in p['tickets'] if num in t['numbers']]
    roles=('勝つ比較の候補' if num in o['win_candidates'] else '勝つ軸未決定／個別の勝ち固定なし')+'。'+('圏内比較の候補' if num in o['place_candidates'] else '圏内の優先候補には固定しない')+'。'
    if alternative:roles+='入替え別案の相手に包含（着順固定ではない）。'
    if h['status_at_snapshot']=='withdrawn':roles='取消。順位・買い目の対象外。'
    specific=o['notes'][num]['ticket_review']
    if main:ticket='本線で採用：'+','.join('−'.join(map(str,t['numbers'])) for t in main)+'。条件未確認なら購入しない。懸念：'+h['risk']
    elif specific:ticket=specific
    elif not plans:ticket='レース全体を見送り。個別懸念：'+h['risk']+' 能力材料は評価欄に保持。'
    else:ticket='本線不採用。個別懸念：'+h['risk']+' 本線は'+o['decision']+' 上記能力材料は消さない。'
    return dict(suitability=suitability,recency=recency,last_actual_start=date.date().isoformat() if date else None,days_since_actual_start=interval,position=position,roles=roles,ticket_review=ticket)

def formation_review(r,o,v,n):
    horses={h['number']:h for h in r['horses']};active=o['order'];reviews=[];baselines=[]
    for kind in ['quinella','trio','wide']:
        actual=[p for p in r['bet_plans'] if p['kind']==kind]
        for p in actual or [None]:
            if p:
                groups=p['groups']; nums=list(dict.fromkeys(x for g in groups for x in g)); decision=p['role']; tickets=[t['numbers'] for t in p['tickets']]
            else:
                groups=[];nums=[];decision='skip';tickets=[]
            axis=set(groups[0] if kind in ['quinella','trio'] and groups else set.intersection(*(set(g) for g in groups)) if kind=='wide' and groups else [])
            role=[]
            for x in nums:
                compared=[y for y in dict.fromkeys(active[:7]+o['win_candidates']+o['place_candidates']) if y!=x]
                refs=list(dict.fromkeys(z for y in [x]+compared for z in horses[y]['evidence_refs']))
                role.append(dict(number=x,role=('top_two_axis' if kind=='quinella' else 'top_three_axis') if x in axis else 'counterpart',compared_with=compared,reason=o['notes'][x]['ticket_review']+' 役割比較：'+o['role_detail'],evidence_refs=refs))
            excluded=[dict(numbers=x,reason=why,evidence_refs=list(dict.fromkeys(z for y in x for z in horses[y]['evidence_refs']))) for x,why in EXCLUDED.get((v,n,kind),[])]
            refs=list(dict.fromkeys(z for x in nums for z in horses[x]['evidence_refs']))
            reviews.append(dict(kind=kind,groups=groups,decision=decision,linked_plan_id=p['plan_id'] if p else None,reason=o['decision'] if p else o['role_detail']+' 固定軸・点数・未知条件・価格・予算を比較してこの券種は掲載購入案に採用しない。',role_reviews=role,
                scenario_checks=[dict(scenario='main',decision='keep' if p else 'skip',description=o['pace'],simultaneous_combinations=tickets,reason=o['role_detail'],evidence_refs=refs,collapse_conditions=o['alternate']),dict(scenario='alternate',decision='skip',description=o['alternate'],simultaneous_combinations=[e['numbers'] for e in excluded],reason='この展開を疑う場合は点数を追加せず見送り。掲載点で取れない組合せを含む。',evidence_refs=refs,collapse_conditions=o['alternate'])],excluded_combinations=excluded))
            if p:
                popular=sorted(active,key=lambda x:(horses[x]['market']['win'] is None,horses[x]['market']['win'] or 999999,x))
                for label,order in [('fixed_total_order',active),('saved_win_market_order',popular)]:
                    count=p['points']
                    if kind=='quinella':combos=quin(*order[:4]); bg=[order[:2],order[:4]]
                    elif kind=='trio':combos=trio(order[0],order[1:5],order[1:5]);bg=[order[:1],order[1:5],order[1:5]]
                    else:
                        combos=[tuple(sorted(c)) for c in __import__('itertools').combinations(order[:3],2)] if p['method']=='box' else [tuple(sorted((order[0],order[i+1]))) for i in range(count)]
                        bg=[list(c) for c in combos]
                    market=json.loads((ROOT/v/'prices.json').read_text(encoding='utf-8'))[f'{kind}{n}']; bt=[]
                    for j,c in enumerate(combos):
                        pr=market['prices'].get('-'.join(map(str,c)),{'raw':'未取得','lower':None,'upper':None});floor=p['tickets'][j]['minimum_odds']
                        bt.append(dict(numbers=list(c),example_stake_yen=100,minimum_odds=floor,price=pr,price_condition_at_snapshot=None if pr['lower'] is None else pr['lower']>=floor))
                    assert len(bt)==count
                    baselines.append(dict(plan_id=p['plan_id'],method=label,kind=kind,groups=bg,tickets=bt,points=count,cost_yen=count*100,price_rule=p['price_rule'],checked_at=FIXED,popularity_tie_break='同オッズは馬番順。価格未取得は末尾、低能力の意味ではない。',note='同点数・同費用の診断基準。予想の購入案ではない。'))
    return dict(objective='hit_within_fixed_budget',reviewed_at=FIXED,plans=reviews,diagnostic_baselines=baselines,missing=['調教・パドック・最終馬場・最終取消・締切前価格は未確認。確認できなければ見送り。','実購入額・実際の券種配分は未確認。金額は例。'])

def build():
    races=[];excluded=[];sources=[]
    for v,label,code in [('kochi','高知',31),('saga','佐賀',32)]:
        cards=json.loads((ROOT/v/'cards.json').read_text(encoding='utf-8'))
        markets=json.loads((ROOT/v/'prices.json').read_text(encoding='utf-8'))
        manifest=json.loads((ROOT/v/'sources.json').read_text(encoding='utf-8'))
        for s in manifest.values():
            assert '2026%2F10%2F18' in s['url']
            assert hashlib.sha256((ROOT/v/s['saved_file']).read_bytes()).hexdigest()==s['sha256']
            assert datetime.fromisoformat(s['retrieved_at'])<=NOW
        sources.extend(source(s,v) for s in manifest.values())
        for r in cards:
            n=r['race'];uid=f'nar-{DATE}-{v}-r{n}';start=DATE+'T'+r['start']+':00+09:00'
            if datetime.fromisoformat(start)<=NOW+timedelta(minutes=5):
                excluded.append(dict(race_uid=uid,venue_key=v,venue=label,race_no=n,start_at=start,reason='発走前の確認・公開時間を確保できないため予想対象外。'))
                continue
            o=RACES[v,n];latest=markets[f'latest{n}'];lookup={h['number']:h for h in latest['horses']}
            r.update(race_uid=uid,race_no=n,official_race_id=f'{DATE}/{code}/{n}',source_race_id={'provider':'NAR','id':f'{DATE}/{code}/{n}'},
                start_at=start,fixed_at=FIXED,source_checked_at=latest['source']['retrieved_at'],sources=[source(r['source'],v),source(latest['source'],v)],
                distance_m=r['distance'],surface='dirt',class_text=r['name'],field_size_at_sale_start=None,model_version='NAR-manual-20261018.1')
            r['market']=dict(latest,source=source(latest['source'],v));r['analysis']={k:val for k,val in o.items() if k not in ('notes','order')}
            r['analysis'].update(volatility='高' if o['confidence']=='低' else '中',popular_compare=POPULAR_COMPARE[v,n],confidence_definition='比較材料の揃い方を示す主観区分。的中確率ではない。',volatility_definition='初条件・休養・先行競合から見た不確実性。数値的な荒れ確率ではない。')
            for h in r['horses']:
                number=h['number'];m=lookup[number]
                for p in h['past']:
                    past_date=re.search(r'(\d{2})\.(\d{2})\.(\d{2})',p['overview'])
                    if past_date:assert '20'+past_date[1]+'-'+past_date[2]+'-'+past_date[3]<DATE
                assert h['name']==m['name'],(uid,number,'identity')
                cancelled='取消' in (h['changes']+m['changes']) or '除外' in (h['changes']+m['changes'])
                rank=None if cancelled else o['order'].index(number)+1
                h.update(market=m,card_carried_weight_raw=h['carried_weight'],carried_weight=m['weight'],jockey=m['jockey'],trainer=m['trainer'],
                    source_horse_id={'provider':'NAR','url':'https://www.keiba.go.jp/KeibaWeb/'+h['horse_url'].removeprefix('../')},
                    status_at_snapshot='withdrawn' if cancelled else 'declared',score=None if cancelled else 90-2*rank,score_definition=DEFINITION,rank=rank,
                    mark='取消' if cancelled else (['◎','○','▲','☆','△','△'][rank-1] if rank<=6 else '注' if rank<=8 else '無印'),
                    reason=o['notes'][number]['reason'],risk=o['notes'][number]['risk'],reasons=[o['notes'][number]['reason']],risks=[o['notes'][number]['risk']],
                    missing=['調教・パドックを直接確認していない','当日状態・最終オッズ・最終取消は未確認'],
                    evidence_refs=list(dict.fromkeys(p['run_id'] for p in h['past'])),model_features={'method':'manual_relative_order','class_numeric_conversion':None})
                if rank==1 and o['confidence']=='低':h['mark']='暫定◎'
                text=unicodedata.normalize('NFKC',h['reason']);titles=unicodedata.normalize('NFKC',' '.join(p['name'] for p in h['past']))
                missing_classes=[x for x in re.findall(r'(?<![A-Za-z])[ABC][123](?!\d)',text) if x not in titles]
                AUDIT.append(dict(race_uid=uid,number=number,name=h['name'],reason=h['reason'],risk=h['risk'],record_raw=h['record'],evidence=h['past'],missing_reason_class=missing_classes,card_source=source(r['source'],v)))
                assert not missing_classes,(uid,number,'reason class absent in saved past',missing_classes)
            active={h['number'] for h in r['horses'] if h['status_at_snapshot']=='declared'}
            assert set(o['order'])==active,(uid,'all active runners')
            assert set(o['notes'])=={h['number'] for h in r['horses']}
            priced=[h for h in r['horses'] if h['market']['win']]
            r['favorite_at_snapshot']=[h['number'] for h in priced if h['market']['win']==min(x['market']['win'] for x in priced)] if priced else []
            r['bet_plans']=[]
            for i,(role,kind,tickets,minimum,stake) in enumerate(BETS.get((v,n),[]),1):
                m=markets[f'{kind}{n}'];ts=[]
                for j,numbers in enumerate(tickets):
                    numbers=list(numbers) if kind=='trifecta' else sorted(numbers)
                    assert set(numbers)<=active and len(numbers)==len(set(numbers))
                    price=m['prices'].get('-'.join(map(str,numbers)),{'raw':'未取得','lower':None,'upper':None})
                    floor=minimum[j] if isinstance(minimum,list) else minimum
                    ok=None if price['lower'] is None else price['lower']>=floor
                    ts.append(dict(numbers=numbers,example_stake_yen=stake,minimum_odds=floor,price_condition_at_snapshot=ok,
                        market={'lower_odds':price['lower'],'upper_odds':price['upper'],'checked_at':m['source']['retrieved_at'],'source':source(m['source'],v)},
                        price=price,snapshot_label=m['page_time_raw'],source=source(m['source'],v),actual_purchase=None,
                        decision_at_snapshot='価格のみ達成・直前条件未確認' if ok else '価格未達・見送り' if ok is False else '未取得・見送り'))
                floor_payment=min(t['minimum_odds']*stake for t in ts)
                r['bet_plans'].append(dict(plan_id=f'{uid}-{i}',role=role,selected_for_example=role=='main',kind=kind,type={'wide':'ワイド','trio':'三連複','trifecta':'三連単','quinella':'馬連複'}[kind],number_type='horse',ordered=kind=='trifecta',
                    method='box' if kind=='wide' and len(ts)==3 else 'formation' if kind in ('trio','quinella') else 'individual',groups=GROUPS.get((v,n,kind),tickets),price_rule='all_tickets_required' if kind in ('trio','quinella') else 'individual',tickets=ts,points=len(ts),maximum_example_yen=stake*len(ts),
                    price_eligible_example_yen=(stake*len(ts) if all(t['price_condition_at_snapshot'] is True for t in ts) else 0) if kind in ('trio','quinella') else sum(t['example_stake_yen'] for t in ts if t['price_condition_at_snapshot'] is True),reason=o['decision'],
                    one_hit_at_floor=f'下限価格で1点だけ的中した場合の表示倍率からの払戻目安は最低{floor_payment:,.0f}円、全点費用は{stake*len(ts):,}円。保存価格は変動し、最終払戻ではない。',
                    stop_conditions=['発走・締切を過ぎた','対象馬の取消・除外','直前オッズが下限未満','直前の状態・馬場を確認できない'],execution='例示のみ。実購入未記録。別案は当該レースの本線と入替え、重ね買いしない。'))
            r['analysis']['formation_review']=formation_review(r,o,v,n)
            for plan in r['analysis']['formation_review']['plans']:
                used=set(z for g in plan['groups'] for z in g)
                if not used:continue
                plan['counterpart_exclusions']=[dict(number=h['number'],compared_with=sorted(used),reason=o['notes'][h['number']]['ticket_review'],evidence_refs=list(dict.fromkeys(z for y in r['horses'] if y['number'] in used|{h['number']} for z in y['evidence_refs']))) for h in r['horses'] if h['number'] not in used]
            r['analysis']['fact_checks']=[dict(number=h['number'],reason=h['reason'],evidence_refs=h['evidence_refs'],history_audit=h['history_audit'],status='根拠走の級・距離・着順と同走IDを人手で照合。自由文全体を自動検証した意味ではない。') for h in r['horses']]
            for h in r['horses']:h['comparison']=comparison(h,r,o,r['bet_plans'])
            r['source']=source(r['source'],v);r['bets']=r['bet_plans'];races.append(r)
    for v,label,code in [('kochi','高知',31),('saga','佐賀',32)]:
        for n in range(1,11):excluded.append(dict(race_uid=f'nar-{DATE}-{v}-r{n}',venue_key=v,venue=label,race_no=n,reason='確認開始時点で発走済み、または公開時間を確保できないため対象外。'))
    main=sum(p['maximum_example_yen'] for r in races for p in r['bet_plans'] if p['selected_for_example'])
    total_max=sum(max([sum(p['maximum_example_yen'] for p in r['bet_plans'] if p['role']=='main')]+[p['maximum_example_yen'] for p in r['bet_plans'] if p['role']=='alternative']) for r in races)
    d=dict(schema_version='kba.forecast/1',document_type='prediction',authority='nar',date_jst=DATE,forecast_version=VERSION,version=VERSION,model_version='NAR-manual-20261018.1',fixed_at=FIXED,phase='remaining_races',venue='高知・佐賀',
        venues=[dict(venue_key=v,label=label,baba_code=code) for v,label,code in [('kochi','高知',31),('saga','佐賀',32)]],races=races,excluded_races=excluded,sources=sources,additional_sources=EXTRA,
        budget=dict(mode='example',day_limit_yen=1000,selected_main_yen=main,maximum_with_replacements_yen=total_max,price_eligible_main_yen=sum(p['price_eligible_example_yen'] for r in races for p in r['bet_plans'] if p['role']=='main'),note='全点100円。価格を満たしても直前条件は未確認。見送った資金を他レースへ再配分しない。',venues={v:sum(p['maximum_example_yen'] for r in races if r['venue_key']==v for p in r['bet_plans'] if p['role']=='main') for v in ['kochi','saga']}),
        model=dict(definition=DEFINITION,calibrated=False,expected_value=None,limitations=['血統・調教・パドックの専門的評価は未実施','本日の対象11Rの結果は取得・採用していない。全対象の発走前に固定。本日の前レース結果・映像を用いた馬場傾向の判定は未実施','馬場は出馬表取得時点。ナイター後半の変化は未確認','過去走は出馬表近5走と公式履歴の2026年同場同距離の追加確認。追加走を区別し、同じ走の時計・着差・上がりを独立票に数えない','早期オッズは少投票で変動が大きい。購入時の価格・取消・状態の確認は別途必要']),
        improvements=['10/11の反省：除外馬と採用相手を直接比較し、状態未知と能力を分離。全25頭の2026年公式履歴を追加確認','高知は単独軸を強く置けずワイド3頭BOX。佐賀の三連複は相手4頭の全ペア6点で差し馬5・9の同時好走を群で排除しない','10/8の反省に沿い、全頭の能力・適性・実出走間隔・位置取り・買い目への採否を発走前に保存','勝つ候補と圏内候補をレースごとに人手で別記。総合順位から勝ち軸説明を自動作成しない','3歳限定戦・他場の級は原文を保持。本文の級の照合表と原文5走を保存','転入・休養・異距離の凡走を低能力へ置き換えず、採用馬と除外馬へ同じ状態確認基準を使う','指定形式を参考に役割を比較。今回は本線ワイド、佐賀は相手4頭の三連複6点を入替え別案。12点を埋めるために根拠の弱い相手を足さない。群制限で取れない組合せも保存','手順の変更は適用したが、的中率・回収率の改善効果と確率校正は未検証'],actual_purchase=None,hash_method='utf8-no-bom-lf-sha256')
    assert main<=total_max<=1000
    assert races and all(datetime.fromisoformat(r['start_at'])>NOW+timedelta(minutes=5) for r in races)
    return d

if __name__=='__main__':
    freeze='--freeze' in sys.argv
    folder=PROJECT/'outputs/nar20261018' if freeze else ROOT/'draft'
    if freeze and folder.exists():raise RuntimeError('Frozen original already exists')
    d=build();folder.mkdir(parents=True,exist_ok=True);jp=folder/(NAME+'.json');hp=folder/(NAME+'.html')
    jp.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');hp.write_text(render(d,jp.name).replace('馬連5点・三連複12点は全点が下限以上の場合だけ候補。','三連複などのフォーメーションは、掲載した全点が下限以上の場合だけ候補。').replace('投票の少ない早期価格で、最終人気ではありません。','保存時点の価格で、最終人気・最終オッズではありません。'),encoding='utf-8')
    audit=dict(date=DATE,fixed_at=FIXED,method='全頭の人手比較と、級・年齢条件・距離・着順の原文参照表。級文字列の機械照合は補助であり、勝率検証ではない。',additional_sources=EXTRA,items=AUDIT)
    (folder/'fact_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if freeze:
        shared=SHARED/'outputs/nar20261018';shared.mkdir(parents=True,exist_ok=False)
        for dest in [folder/'sources',shared/'sources']:
            for v in ['kochi','saga']:shutil.copytree(ROOT/v,dest/v,dirs_exist_ok=False)

        for p in [jp,hp,folder/'fact_audit.json']:shutil.copy2(p,shared/p.name)
        for name in ['opinions.py','build_day.py','fetch_prices_freeze.py','fetch_prices_confirm.py','collect_today.py','history.json']:
            shutil.copy2(ROOT/name,folder/name);shutil.copy2(ROOT/name,shared/name)
        record={'fixed_at':FIXED,'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [jp,hp,folder/'fact_audit.json']}}
        (folder/'freeze_record.json').write_text(json.dumps(record,indent=2),encoding='utf-8');shutil.copy2(folder/'freeze_record.json',shared/'freeze_record.json')
    print(json.dumps(dict(folder=str(folder),fixed_at=FIXED,races=len(d['races']),horses=sum(len(r['horses']) for r in d['races']),budget=d['budget']),ensure_ascii=False))
