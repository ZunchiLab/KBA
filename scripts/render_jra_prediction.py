"""JRA view of the shared day layout; forecast inputs remain immutable."""
from pathlib import Path
from html import escape
from hashlib import sha256
import json,re
from render_day_prediction import render as shared_render
ROOT=Path(__file__).resolve().parents[1]
KINDS={'win':'単勝','place':'複勝','wide':'ワイド','quinella':'馬連','exacta':'馬単','trio':'三連複','trifecta':'三連単','bracket_quinella':'枠連'}
def legacy_result(d):
    return dict(schema_version=1,authority='jra',date_jst=d['date_jst'],venue_key=d['venue_key'],baba_code=5 if d['venue_key']=='tokyo' else 8,forecast_version=d['forecast_ref']['version'],forecast_sha256=d['forecast_ref']['sha256'],updated_at=d['updated_at'],last_poll_at=d['last_poll_at'],complete=all(r['status'] in ['confirmed','cancelled'] for r in d['races']),refresh_interval_minutes=2,races=[dict(race=r['race_no'],start_at=r['start_at'],status=r['status'],source=r.get('source'),refresh_error=r.get('refresh_error'),rows=[dict(number=h['number'],name=h['name'],finish=h['finish'] if h['finish'] is not None else h.get('official_status_text','未確定')) for h in r['rows']],refunds=[dict(kind=KINDS.get(p['kind'],p['kind']),numbers=p['numbers'],combination='−'.join(map(str,p['numbers'])),yen_per_100=p['yen_per_100']) for p in r['payouts']]) for r in d['races']])
def render(d,json_name,results=None):
    results={k:legacy_result(v) if v.get('schema_version')=='kba.results/1' else v for k,v in (results or {}).items()}
    s=shared_render(d,json_name,results)
    s=s.replace('園田・大井','東京・京都').replace('園田と大井。','東京と京都。').replace('NAR ·','JRA ·').replace('昨日の反省と、今日の評価方法','これまでの反省と、今日の評価方法')
    s=s.replace('全頭評価 / 少点数の本線 / 三連単の別案','全24レース・315頭 / 勝つ候補と圏内候補 / 公式出馬表で照合')
    s=s.replace('金額はすべて例・全点100円。','金額はすべて例。点ごとの額は買い目表を参照。')
    s=s.replace('自信度は比較材料の揃い方、波乱度は未知条件・休養・先行競合の主観評価です。勝率・期待値は推定していません。','自信度は比較材料の揃い方、波乱度は未知条件・休養・先行競合の主観評価です。荒れ確率は未校正のため未算定。勝率・期待値は推定していません。比較指数と人手の印の違いは各馬へ記録しています。')
    s=s.replace('本線／別案／見送り','本線／別案／見送り')
    s=s.replace('三連単などの別案','本線との入替え参考案')
    s=s.replace('前日','前日')
    for r in d['races']:
        for p in r['bet_plans']:
            old=f'{p["points"]}点 × 100円 = 最大{p["maximum_example_yen"]:,}円'
            stakes=set(t['example_stake_yen'] for t in p['tickets']);amount=str(next(iter(stakes))) if len(stakes)==1 else '点別'
            s=s.replace(old,f'{p["points"]}点 × {amount}円 = 最大{p["maximum_example_yen"]:,}円')
            if p['role']=='reference':
                s=s.replace('value="'+p['plan_id']+'" data-cost="'+str(p['maximum_example_yen'])+'" >別案','value="'+p['plan_id']+'" data-cost="'+str(p['maximum_example_yen'])+'" >参考案')
            src=p['tickets'][0]['source'];token=src.get('request_fields',{}).get('cname')
            if token:
                old=f'<a href="{escape(src["url"],quote=True)}">公式オッズ</a>'
                new=f'<form class="official-market" action="{escape(src["url"],quote=True)}" method="post" target="_blank"><input type="hidden" name="cname" value="{escape(token,quote=True)}"><button type="submit">JRA公式オッズを開く</button></form>'
                s=s.replace(old,new,1)
        for h in r['horses']:
            label=f'{h["rank"]}位 / 指数{h["score"]}' if h['rank'] else '評価対象外'
            new=f'総合{h["rank"]}位 / 比較指数{h["score"] if h["score"] is not None else "保留"}'
            if h['score_method']=='market_reference':new=f'市場参考{h["rank"]}位 / 参考値{h["score"]}'
            new+=f' · 勝{h["win"] if h["win"] is not None else "未算定"} / 圏{h["place"] if h["place"] is not None else "未算定"}'
            # Replace within this horse only, because equal scores can occur in other races.
            pattern=r'(<details class="horse" data-number="'+str(h['number'])+r'">.*?<small>)'+re.escape(label)
            # Scope by race to avoid unrelated identical horse numbers.
            a=s.index('<article class="race" id="'+r['race_uid']+'"');b=s.index('</article>',a)
            fragment=s[a:b];fragment=re.sub(pattern,lambda m:m[1]+new,fragment,count=1,flags=re.S);s=s[:a]+fragment+s[b:]
    # Clarify references vs selected main plans, and provide an immediate short summary.
    s=s.replace('全頭の印・評価・着順','全頭の印・評価・着順（総合判断順）')
    for r in d['races']:
        if not any(p['selected_for_example'] for p in r['bet_plans']):
            a=s.index('<article class="race" id="'+r['race_uid']+'"');b=s.index('</article>',a);f=s[a:b].replace('条件付き購入候補','本線見送り・参考案のみ' if r['bet_plans'] else '馬券見送り');s=s[:a]+f+s[b:]
        if r['bet_plans']:
            uid=r['race_uid'];a=s.index('<fieldset class="plan-choice"><legend>',s.index('<article class="race" id="'+uid+'"'));b=s.index('</fieldset>',a)
            if not any(p['selected_for_example'] for p in r['bet_plans']):s=s[:a]+s[a:b].replace('value="skip" data-cost="0"','value="skip" data-cost="0" checked')+s[b:]
    css=(ROOT/'assets/css/day-report.css').read_text(encoding='utf-8')+'\nbody{overflow-wrap:anywhere}.hero{background:linear-gradient(125deg,#17332d,#246854)}.quick-picks{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px}.official-market{display:inline}.race-nav-note{font-size:.78rem}.comparison-table{min-width:1100px}@media(max-width:700px){.comparison-table{min-width:0}}'
    s=re.sub(r'<link rel="stylesheet"[^>]+>',lambda m:'<style>'+css+'</style>',s,count=1)
    s=re.sub(r'<script src="../assets/js/day-report.js[^>]+></script>','',s,count=1)
    js=(ROOT/'assets/js/jra-day-report.js').read_text(encoding='utf-8')
    s=s.replace('</body>', '<script>'+js+'</script></body>')
    # The shared browser code uses this extra discriminator for result paths.
    pattern=r'(<script type="application/json" id="day-forecast">)(.*?)(</script>)'
    def config(m):
        c=json.loads(m[2]);c['authority']='jra';return m[1]+json.dumps(c,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')+m[3]
    s=re.sub(pattern,config,s,flags=re.S)
    quick='<section class="panel"><h2>本線の一覧：価格条件付き・金額は例</h2><div class="quick-picks">'+''.join('<a href="#'+r['race_uid']+'"><b>'+r['venue']+str(r['race'])+'R</b> '+r['start']+'<br>'+escape(' / '.join(p['type']+' '+', '.join('−'.join(map(str,t['numbers']))+' 最低'+str(t['minimum_odds'])+'倍' for t in p['tickets']) for p in r['bet_plans'] if p['selected_for_example']))+'</a>' for r in d['races'] if any(p['selected_for_example'] for p in r['bet_plans']))+'</div><p class="muted">朝の確認版です。午後のオッズ・馬場・取消・状態は購入直前に再確認。満たさなければ見送り、余りは再配分しません。</p></section>'
    s=s.replace('<section class="panel" id="results-panel">',quick+'<section class="panel" id="results-panel">',1)
    w=d.get('win5',{});s=s.replace('<footer class="panel">','<section class="panel"><h2>WIN5：今回は見送り</h2><p>'+escape(w.get('note','未作成'))+'</p><ul>'+''.join('<li>'+escape(x['label'])+'：'+escape('・'.join(map(str,x['candidates'])))+'</li>' for x in w.get('legs',[]))+'</ul></section><footer class="panel">',1)
    return s
def render_day_snapshot(forecast):
    path=ROOT/forecast;text=path.read_text(encoding='utf-8-sig').replace('\r\n','\n');d=json.loads(text);digest=sha256(text.encode()).hexdigest();results={}
    for v in d['venues']:
        p=ROOT/'data/results/jra'/d['date_jst']/d['forecast_version']/(v['venue_key']+'.json')
        if p.exists():
            result=json.loads(p.read_text(encoding='utf-8'));assert result['forecast_ref']['sha256']==digest and result['forecast_ref']['version']==d['forecast_version'];results[v['venue_key']]=result
    path.with_suffix('.html').write_text(render(d,path.name,results),encoding='utf-8',newline='\n')
