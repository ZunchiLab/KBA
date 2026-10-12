"""Compact JRA layout, enabled only by a new forecast presentation field."""
from pathlib import Path
from html import escape
import json
from render_day_prediction import comparison_table, formation_section, past_item, result_for, finish

ROOT=Path(__file__).resolve().parents[1]
E=lambda x:escape(str(x),quote=True)
safe=lambda x:json.dumps(x,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')

def brief_plan(p):
    if p['method']=='formation':
        return ' − '.join(','.join(map(str,g)) for g in p['groups'])
    return ' / '.join('−'.join(map(str,t['numbers'])) for t in p['tickets'])

def plan_html(p,visible=False):
    floors=sorted(set(t['minimum_odds'] for t in p['tickets']))
    floor=' / '.join(f'{x:.1f}' for x in floors)
    count=sum(t['price_condition_at_snapshot'] is True for t in p['tickets'])
    ok=count==p['points']
    label='本線' if p['selected_for_example'] else '入替え案' if p['role']=='alternative' else '参考・本線見送り'
    out=[f'<section class="bet-plan" data-plan="{E(p["plan_id"])}"><div class="row"><h3>{label} · {E(p["type"])}</h3><button class="copy-plan" data-plan-id="{E(p["plan_id"])}" type="button">コピー</button></div>',
         f'<p class="formation"><b>{E(brief_plan(p))}</b></p>',
         f'<p class="plan-meta">{p["points"]}点 × 100円 = <b>{p["maximum_example_yen"]:,}円例</b> · 全点{floor}倍以上</p>',
         f'<p class="price-status {"ok" if ok else "wait"}">保存価格 {count}/{p["points"]}点達成 · {"直前確認で判断" if ok else "この案は見送り"}</p>']
    # Keep the full individual tickets, saved prices and timestamps reviewable.
    rows=[]
    for t in p['tickets']:
        rows.append('<tr><th>'+E('−'.join(map(str,t['numbers'])))+'</th><td>'+E(t['price']['raw'])+'</td><td>'+f'{t["minimum_odds"]:.1f}'+'</td></tr>')
    table='<table class="tickets"><thead><tr><th>買い目</th><th>保存倍率</th><th>下限</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table>'
    out.append('<details><summary>保存価格・全'+str(p['points'])+'点</summary>'+table+'</details>')
    source=p['tickets'][0]['source'];token=source.get('request_fields',{}).get('cname')
    market=(f'<form class="official-market" action="{E(source["url"])}" method="post" target="_blank"><input type="hidden" name="cname" value="{E(token)}"><button type="submit">公式オッズ</button></form>' if token else f'<a href="{E(source["url"])}">公式オッズ</a>')
    out.append('<details class="plan-conditions"><summary>購入条件・確認時刻</summary><p>'+E(p['reason'])+'</p><p>'+E(p['tickets'][0]['snapshot_label'])+'／取得 '+E(source['retrieved_at'])+'</p><p>取消なし・馬場と当日状態を確認・締切前・全点が下限以上。未確認や1点でも未達なら案全体を見送り。金額は例、実購入未記録。</p><p>'+E(p.get('one_hit_at_floor',''))+'</p>'+market+'</details>')
    out.append(f'<p class="plan-result" data-plan-result="{E(p["plan_id"])}">結果待ち · 実購入未記録</p></section>')
    return ''.join(out)

def render(d,json_name,results):
    b=d['budget'];n=sum(len(r['horses']) for r in d['races']);selected=[r for r in d['races'] if any(p['selected_for_example'] for p in r['bet_plans'])]
    css=(ROOT/'assets/css/jra-compact.css').read_text(encoding='utf-8')
    parts=[f'<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#173b34"><title>{E(d["date_jst"])} JRA 本気予想</title><style>{css}</style></head><body class="compact"><main>',
           f'<header class="hero"><div class="row"><h1>{E(d["date_jst"][5:].replace("-","/"))} JRA 本気予想</h1><a href="../index.html">一覧</a></div><p>東京・京都 · 全24R / {n}頭 · {E(d["fixed_at"][11:16])} JST固定</p></header>',
           '<nav class="sticky" aria-label="競馬場とレース"><div id="venue-tabs" role="tablist">'+''.join(f'<button role="tab" type="button" id="tab-{v["venue_key"]}" aria-controls="venue-{v["venue_key"]}" aria-selected="false" data-venue="{v["venue_key"]}">{E(v["label"])}</button>' for v in d['venues'])+'</div>']
    for v in d['venues']:
        parts.append(f'<div class="race-jumps" data-venue="{v["venue_key"]}" aria-label="{E(v["label"])}レース番号">'+''.join(f'<a href="#{r["race_uid"]}" data-race-uid="{r["race_uid"]}">{r["race"]}</a>' for r in d['races'] if r['venue_key']==v['venue_key'])+'</div>')
    parts.append('<div class="filters"><input id="horse-search" type="search" aria-label="馬名・レース検索" placeholder="馬名・レース検索"><select id="race-filter" aria-label="レース表示"><option value="all">全レース</option><option value="buy">本線候補</option><option value="future">発走前</option></select></div></nav>')
    parts.append('<section class="day-summary"><details><summary>本線'+str(len(selected))+'R · 全点 '+f'{b["selected_main_yen"]:,}'+'円例 <span>一覧・予算</span></summary><div class="quick-picks">')
    for r in selected:
        p=next(p for p in r['bet_plans'] if p['selected_for_example'])
        parts.append(f'<a href="#{r["race_uid"]}"><b>{E(r["venue"])}{r["race"]}R</b> {E(r["start"])} · {E(p["type"])}<br>{E(brief_plan(p))} · {p["maximum_example_yen"]:,}円</a>')
    parts.append(f'</div><p>各100円の例。上限例{b["day_limit_yen"]:,}円／保存価格の全点達成分{b["price_eligible_main_yen"]:,}円。直前条件は未確認。余りは再配分しません。</p><div id="plan-total" role="status">仮プラン {b["selected_main_yen"]:,}円</div><a href="../tools/bet-planner.html">購入記録の補助</a></details></section>')
    parts.append('<section class="result-toolbar" id="results-panel"><button id="refresh-results" type="button">結果を更新</button><details><summary>取得状況</summary><p id="result-status" role="status" aria-live="polite">'+E('保存結果を表示' if results else '発走前・結果未取得')+'</p></details></section><p id="empty-state" hidden>該当レースなし</p>')
    for v in d['venues']:
        key=v['venue_key'];vr=[r for r in d['races'] if r['venue_key']==key]
        parts.append(f'<section class="venue-panel" id="venue-{key}" role="tabpanel" aria-labelledby="tab-{key}">')
        for r in vr:
            uid=r['race_uid'];a=r['analysis'];res=result_for(results,key,r['race']);main=[p for p in r['bet_plans'] if p['selected_for_example']]
            search=' '.join([r['name'],str(r['race'])+'R']+[h['name'] for h in r['horses']])
            confidence=a['confidence'].replace('（主観）','');decision='条件付き本線' if main else '見送り'
            surface={'turf':'芝','dirt':'ダ','hurdle':'障'}[r['surface']]
            going=r['going'].replace('ダート','').replace('芝','').replace('：','').strip()
            level=r['grade'] or r['class_text']
            parts.append(f'<article class="race" id="{uid}" data-venue="{key}" data-start="{E(r["start_at"])}" data-search="{E(search)}" data-bets="{str(bool(main)).lower()}"><header class="race-head"><div class="row"><b>{E(v["label"])} {r["race"]}R · {E(r["start"])}</b><span class="decision-badge {"buy" if main else "skip"}">{decision}</span></div><h2>{E(r["name"])}</h2><p>{E(level)} · {surface}{r["distance_m"]}m · {E(going)} · {len(r["horses"])}頭 <span class="clock-state"></span></p><div class="badges"><span>自信 {E(confidence)}</span><span>波乱 {E(a["volatility"])}</span><small>主観評価</small></div></header><div class="race-body">')
            secondary=[]
            if not main:parts.append('<p class="one-line">'+E(a['headline'])+'</p>')
            for p in main:parts.append(plan_html(p,True))
            if not main:parts.append('<p class="skip-reason">'+E(a.get('short_skip',a['decision']))+'</p>')
            secondary.append('<details class="analysis"><summary>展開・軸・除外理由</summary><p>'+E(a['headline'])+'</p><p><b>勝つ候補</b> '+E(a['win_view'])+'</p><p><b>圏内候補</b> '+E(a['place_view'])+'</p><p><b>主展開</b> '+E(a['pace'])+'</p><p><b>別展開</b> '+E(a['alternate'])+'</p><p>'+E(a['decision'])+'</p><p>'+E(a['popular_compare'])+'</p><p>荒れ確率は未算定。比較指数・自信度は確率ではありません。</p></details>')
            other=[p for p in r['bet_plans'] if not p['selected_for_example']]
            if other:secondary.append('<details class="other-plans"><summary>'+('入替え案' if main else '参考の買い目')+'</summary>'+''.join(plan_html(p) for p in other)+'</details>')
            if r['bet_plans']:
                secondary.append(f'<details class="plan-controls"><summary>仮プランを変更</summary><fieldset class="plan-choice"><legend>費用例の選択・購入ではありません</legend><label><input type="radio" name="{uid}" value="skip" data-cost="0" {"checked" if not main else ""}>見送り</label>')
                for p in r['bet_plans']:secondary.append(f'<label><input type="radio" name="{uid}" value="{p["plan_id"]}" data-cost="{p["maximum_example_yen"]}" {"checked" if p["selected_for_example"] else ""}>{E(p["type"])} {p["maximum_example_yen"]:,}円例</label>')
                secondary.append('</fieldset></details>')
            parts.append('<div class="row horse-toolbar"><h3>全頭の印・スコア</h3><button class="sort-horses" type="button">馬番順</button></div><p class="race-result-status">'+E(res.get('note','結果待ち') if res else '結果待ち')+'</p><div class="horse-columns"><span>印 / 馬番・馬名</span><span>指数</span><span>着順</span></div><div class="all-horses">')
            for h in sorted(r['horses'],key=lambda h:h['rank'] or 999):
                score=h['score'] if h['score'] is not None else '保留';mark=h['mark'].replace('参考','').replace('暫定','');f=finish(res,h)
                if f in ['保存時は発走前','未確定','全着順待ち']:f='—'
                ref_label='市場参考' if h['score_method']=='market_reference' else '暫定比較' if r['surface']=='hurdle' else '比較指数'
                parts.append(f'<details class="horse" data-number="{h["number"]}"><summary><span class="mark">{E(mark)}</span><span class="horse-label"><b>{h["number"]} {E(h["name"])}</b><small>{h["rank"]}位 · {E(h["style"])}</small></span><b class="score">{E(score)}</b><strong class="horse-finish">{E(f)}</strong></summary><div class="horse-detail"><p>{E(h["jockey"])} · {h["weight"]}kg · 馬体重 {E(h["body"] or "未発表")}</p><p>{ref_label} {E(score)} · 勝比較 {E(h["win"] if h["win"] is not None else "未算定")} / 圏内比較 {E(h["place"] if h["place"] is not None else "未算定")}</p><p><b>根拠</b> {E(h["reason"])}</p><p><b>懸念</b> {E(h["risk"])}</p><p><b>採否</b> {E(h["ticket_review"])}</p><details><summary>過去走と出典</summary><ul>'+''.join(past_item(p) for p in h['past'])+'</ul></details></div></details>')
            parts.append('</div><div class="payouts"></div>'+''.join(secondary))
            parts.append(comparison_table(r)+formation_section(r))
            parts.append('<details class="sources"><summary>出馬表・確認時刻</summary><a href="'+E(r['source']['url'])+'">JRA公式出馬表</a><p>出馬表 '+E(r['source']['retrieved_at'])+'／価格 '+E(r['source_checked_at'])+'</p><p>馬場は出馬表取得時点。取消・馬場・状態・価格は直前再確認。</p></details></div></article>')
        parts.append('</section>')
    # The browser only needs runner identity/rank, ticket plans and timestamps.
    races=[{k:r[k] for k in ['race_uid','venue_key','venue','race','start_at','bet_plans']}|{'horses':[{k:h[k] for k in ['number','name','rank','status_at_snapshot']} for h in r['horses']]} for r in d['races']]
    config=dict(authority='jra',date=d['date_jst'],version=d['forecast_version'],jsonFile=json_name,venues=d['venues'],races=races,budget=b,compact=True)
    digests={value.get('forecast_sha256') for value in results.values()}
    if len(digests)==1:config['forecastSha256']=next(iter(digests))
    parts.append('<footer><details><summary>評価方法・未確認事項・JSON</summary><p>'+E(d['model']['definition'])+'</p><ul>'+''.join('<li>'+E(x)+'</li>' for x in d['model']['limitations'])+'</ul><p>自信・波乱は主観。荒れ確率は未校正のため未算定。事前予想は固定し、結果のみ別更新。</p><p>固定 '+E(d['fixed_at'])+' · '+E(d['forecast_version'])+'</p><a id="forecast-link" href="'+E(json_name)+'">全頭・買い目・比較記録JSON</a></details><noscript>JavaScript無効時は全レースを表示します。</noscript></footer>')
    js=(ROOT/'assets/js/jra-day-report.js').read_text(encoding='utf-8')
    parts.append('<script type="application/json" id="day-forecast">'+safe(config)+'</script><script type="application/json" id="day-results">'+safe(results)+'</script><script>'+js+'</script></main></body></html>')
    return '\n'.join(parts)
