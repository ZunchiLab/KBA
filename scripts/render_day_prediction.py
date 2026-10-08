"""Render a frozen multi-venue forecast, with separate result snapshots."""
from html import escape
from pathlib import Path
from hashlib import sha256
import json

ROOT=Path(__file__).resolve().parents[1]
E=lambda x:escape(str(x),quote=True)
KINDS={'wide':'ワイド','trio':'三連複','trifecta':'三連単'}

def result_for(results,venue,no):
    return next((r for r in results.get(venue,{}).get('races',[]) if r['race']==no),None)

def finish(result,h):
    row=next((r for r in (result or {}).get('rows',[]) if r['number']==h['number']),None)
    if row:return str(row['finish'])+'着' if isinstance(row['finish'],int) else str(row['finish'])
    if h['status_at_snapshot']=='withdrawn':return '取消'
    return {'not_started':'保存時は発走前','confirmed':'未掲載','cancelled':'競走取止','partial':'全着順待ち','error':'取得保留'}.get((result or {}).get('status'),'未確定')

def render(d,json_name,results=None):
    results=results or {};parts=[]
    b=d['budget']
    title=d['date_jst'].replace('-','/')+' 園田・大井の本気予想'
    jumps=''.join('<div class="race-jumps" data-venue="'+v['venue_key']+'" aria-label="'+E(v['label'])+'のレース">'+''.join('<a href="#'+r['race_uid']+'">'+str(r['race'])+'R <small>'+E(r['start'])+'</small></a>' for r in d['races'] if r['venue_key']==v['venue_key'])+'</div>' for v in d['venues'])
    parts.append(f'''<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{E(title)}｜全頭評価・会場タブ</title><link rel="stylesheet" href="../assets/css/day-report.css?v=20261008_2"><script src="../assets/js/day-report.js?v=20261008_2" defer></script></head><body><main>
<header class="hero"><div class="eyebrow">NAR · {E(d['forecast_version'])} · {E(d['date_jst'])}</div><h1>園田と大井。<br>根拠と買い方を、一緒に。</h1><p>全頭評価 / 少点数の本線 / 三連単の別案</p><p class="muted">{E(d['fixed_at'][11:19])} JST固定 · 事前予想は固定、結果のみ別更新</p><a href="../index.html">予想一覧</a> · <a href="{E(json_name)}" id="forecast-link">固定予想JSON</a></header>
<section class="panel"><h2>今日の買い方</h2><div class="stats"><div><b>{b['selected_main_yen']:,}円</b><span>本線を全点買う場合</span></div><div><b>{b['maximum_with_replacements_yen']:,}円</b><span>別案に差し替えた最大額</span></div><div><b>{b['day_limit_yen']:,}円</b><span>1日上限の例</span></div></div><p>金額はすべて例・全点100円。<strong>価格と直前条件を満たした点だけ</strong>が候補です。余った分は買い足しに回しません。</p><p>保存価格で下限達成の本線：{b['price_eligible_main_yen']:,}円分。ただし、状態・最終取消・締切前価格は未確認です。購入済みを意味しません。</p><p>別案はそのレースの本線と<strong>入替え</strong>。BOXは順番違いをカバーしますが、選ばなかった馬が入ると外れます。</p><a href="../tools/bet-planner.html">買い方・予算・購入記録の補助を開く →</a></section>
<section class="panel" id="results-panel"><div class="row"><h2>印と結果</h2><button type="button" id="refresh-results">最新の保存結果を取得</button></div><p id="result-status" role="status" aria-live="polite">{E('会場別の保存結果を表示しています。' if results else 'まだ結果を取得していません。印と馬名は取得前・取得失敗時も表示します。')}</p><p class="muted">ボタンは公式を収集したGitHubの最新保存データを取得します。表示中は約2分ごとにも確認。取得元・確認時刻をレースごとに表示し、既知の結果を消しません。</p></section>
<details class="panel"><summary>昨日の反省と、今日の評価方法</summary><ul>{''.join('<li>'+E(x)+'</li>' for x in d['improvements'])}</ul><p>{E(d['model']['definition'])}</p><ul>{''.join('<li>'+E(x)+'</li>' for x in d['model']['limitations'])}</ul><p>自信度は比較材料の揃い方、波乱度は未知条件・休養・先行競合の主観評価です。勝率・期待値は推定していません。</p><p>対象外：{E(' / '.join(v['label']+' '+','.join(str(x['race_no']) for x in d['excluded_races'] if x['venue_key']==v['venue_key'])+'R' for v in d['venues'] if any(x['venue_key']==v['venue_key'] for x in d['excluded_races'])))}</p><p>発走済み、または直前確認・公開の時間を確保できないレースは後付け予想に含めません。</p></details>
<nav class="sticky" aria-label="競馬場"><div id="venue-tabs" role="tablist">{''.join(f'<button type="button" role="tab" id="tab-{v["venue_key"]}" aria-controls="venue-{v["venue_key"]}" aria-selected="false" data-venue="{v["venue_key"]}">{E(v["label"])}</button>' for v in d['venues'])}</div>{jumps}<div class="row filters"><input id="horse-search" type="search" aria-label="馬名・レースを検索" placeholder="馬名・レース名を検索"><select id="race-filter" aria-label="レース表示"><option value="all">すべて</option><option value="buy">買い目あり</option><option value="future">発走前</option></select></div><div id="plan-total" role="status">仮プラン合計 {b['selected_main_yen']:,}円 / 上限例 {b['day_limit_yen']:,}円</div></nav>''')
    errata_path=ROOT/'data/results/nar'/d['date_jst']/'errata.json'
    if errata_path.exists():
        errata=json.loads(errata_path.read_text(encoding='utf-8'))
        if errata['forecast_version']==d['forecast_version']:
            parts.append('<aside class="panel"><h2>過去走の表記訂正</h2>'+''.join('<p>'+E(c['text'])+'</p>' for c in errata['corrections'])+'</aside>')
    if d.get('revision'):
        parts.append('<aside class="panel"><h2>v2の訂正内容</h2><p>'+E(d['revision']['reason'])+'</p><p>v1は保存しています。結果判明前の訂正です。</p></aside>')
    for v in d['venues']:
        key=v['venue_key'];vr=[r for r in d['races'] if r['venue_key']==key]
        parts.append(f'<section class="venue-panel" id="venue-{key}" role="tabpanel" aria-labelledby="tab-{key}" tabindex="0"><h2 class="venue-title">{E(v["label"])} <small>{len(vr)}レース</small></h2><nav class="race-jumps" aria-label="{E(v["label"])}のレース">'+''.join(f'<a href="#{r["race_uid"]}">{r["race"]}R <small>{E(r["start"])}</small></a>' for r in vr)+'</nav>')
        for r in vr:
            uid=r['race_uid'];a=r['analysis'];res=result_for(results,key,r['race']);ranked=sorted(r['horses'],key=lambda h:h['rank'] or 999)
            search=' '.join([r['name'],str(r['race'])+'R']+[h['name'] for h in r['horses']])
            parts.append(f'<article class="race" id="{uid}" data-venue="{key}" data-race="{r["race"]}" data-start="{r["start_at"]}" data-search="{E(search)}" data-bets="{str(bool(r["bet_plans"])).lower()}"><header class="race-head"><p class="eyebrow">{E(v["label"])} {r["race"]}R · {r["start"]}発走 <span class="clock-state"></span></p><h2>{E(r["name"])}</h2><p>{E(r["distance"])}m · {E(r["going"])}（出馬表取得時） · {len(r["horses"])}頭／取消含む</p><div class="badges"><span>自信度 {E(a["confidence"])}</span><span>波乱度 {E(a["volatility"])}</span><span>{"条件付き購入候補" if r["bet_plans"] else "馬券見送り"}</span></div></header><div class="race-body"><h3>{E(a["headline"])}</h3><div class="scenario"><p><b>本線の展開</b> {E(a["pace"])}</p><p><b>別の展開</b> {E(a["alternate"])}</p></div><p>{E(a["win_view"])}</p><p>{E(a["place_view"])}</p><p class="decision">{E(a["decision"])}</p>')
            if r['bet_plans']:
                parts.append(f'<fieldset class="plan-choice"><legend>仮プランを選ぶ（購入記録ではありません）</legend><label><input type="radio" name="{uid}" value="skip" data-cost="0">見送り</label>')
                for p in r['bet_plans']:
                    parts.append(f'<label><input type="radio" name="{uid}" value="{p["plan_id"]}" data-cost="{p["maximum_example_yen"]}" {"checked" if p["selected_for_example"] else ""}>{"本線" if p["role"]=="main" else "別案"} {p["maximum_example_yen"]:,}円</label>')
                parts.append('</fieldset>')
            for p in r['bet_plans']:
                label='本線' if p['role']=='main' else '別案・本線と入替え'
                parts.append(f'<section class="bet-plan" data-plan="{p["plan_id"]}"><div class="row"><h3>{label} · {E(p["type"])} {"BOX" if p["method"]=="box" else ""}</h3><button type="button" class="copy-plan" data-plan-id="{p["plan_id"]}">買い目をコピー</button></div><p><b>{p["points"]}点 × 100円 = 最大{p["maximum_example_yen"]:,}円</b></p><div class="table-wrap"><table class="tickets"><thead><tr><th>買い目</th><th>保存価格</th><th>最低価格</th><th>判定</th></tr></thead><tbody>')
                for t in p['tickets']:
                    combo=(' → ' if p['ordered'] else ' − ').join(map(str,t['numbers']))
                    label='価格のみ達成' if t['price_condition_at_snapshot'] is True else '見送り' if t['price_condition_at_snapshot'] is False else '未取得'
                    parts.append(f'<tr><th>{E(combo)}</th><td>{E(t["price"]["raw"])}</td><td>{t["minimum_odds"]:.1f}倍</td><td>{label}</td></tr>')
                parts.append(f'</tbody></table></div><p class="muted">{E(p["tickets"][0]["snapshot_label"])} · <a href="{E(p["tickets"][0]["source"]["url"])}">公式オッズ</a>。下限は主観的な購入条件で、期待値の検証値ではありません。</p><p>直前条件：取消なし・状態と馬場を確認・各点の下限以上・締切前。未確認なら見送り。BOXの全組合せを買う必要はありません。</p><p class="plan-result" data-plan-result="{p["plan_id"]}">掲載案の結果：未確定／実購入未記録</p></section>')
            parts.append(f'<h3>全頭の印・評価・着順</h3><button type="button" class="sort-horses">馬番順に切替</button><p class="muted">名前を開くと根拠・懸念・過去走。順位表示指数は能力差や確率を表しません。</p><p class="race-result-status">{E(res.get("note", "結果未取得") if res else "結果未取得")}</p><div class="all-horses">')
            for h in ranked:
                f=finish(res,h);meta=h['market'];details=''.join(f'<li><a href="{E(p["source"])}">{E(p["overview"])}</a><br>{E(p["name"])} · {E(p["time_corners"])} · {E(p["gap_winner"])}</li>' for p in h['past'])
                parts.append(f'<details class="horse" data-number="{h["number"]}"><summary><span class="mark">{E(h["mark"])}</span><span class="horse-label"><b>{h["number"]} {E(h["name"])}</b><small>{str(h["rank"])+"位 / 指数"+str(h["score"]) if h["rank"] else "評価対象外"} · 単{E(meta["win_raw"])}倍</small></span><strong class="horse-finish">{E(f)}</strong></summary><div class="horse-detail"><p>{E(meta["jockey"])} · {E(meta["weight"])}kg · 馬体重 {E(meta["body_weight"] or "未発表")}</p><p><b>評価</b> {E(h["reason"])}</p><p><b>懸念</b> {E(h["risk"])}</p><p class="muted">単勝・馬体重：{E(r["market"]["page_time_raw"])}。調教・パドックは未確認。</p><details><summary>根拠の過去走（同じ走は1件として比較）</summary><ul>{details}</ul></details></div></details>')
            parts.append('</div><div class="payouts"></div><p><a href="'+E(r['source']['url'])+'">公式出馬表・変更情報</a></p></div></article>')
        parts.append('</section>')
    config=dict(date=d['date_jst'],version=d['forecast_version'],jsonFile=json_name,venues=d['venues'],races=d['races'],budget=b)
    safe=lambda x:json.dumps(x,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
    parts.append(f'<p id="empty-state" hidden>該当するレースがありません。</p><footer class="panel"><p>事前予想の版 {E(d["forecast_version"])} · {E(d["fixed_at"])}。結果が出ても印・理由・買い目・保存価格は変更しません。</p><p>馬券購入は20歳以上。購入有無・実収支は未記録です。</p><a href="../docs/common-spec.html">JRA・地方の共通仕様</a></footer><script type="application/json" id="day-forecast">{safe(config)}</script><script type="application/json" id="day-results">{safe(results)}</script></main></body></html>')
    return '\n'.join(parts)

def render_day_snapshot(target):
    path=ROOT/target['forecast'];text=path.read_text(encoding='utf-8-sig').replace('\r\n','\n');d=json.loads(text)
    digest=sha256(text.encode('utf-8')).hexdigest();results={}
    for v in d['venues']:
        rp=ROOT/'data/results/nar'/d['date_jst']
        if d['forecast_version']!='v1':rp=rp/d['forecast_version']
        rp=rp/(v['venue_key']+'.json')
        if not rp.exists():continue
        data=json.loads(rp.read_text(encoding='utf-8'))
        if data['forecast_sha256']!=digest or data['forecast_version']!=d['forecast_version'] or data['date_jst']!=d['date_jst'] or data['venue_key']!=v['venue_key']:raise ValueError('Result snapshot identity mismatch')
        races={r['race']:r for r in d['races'] if r['venue_key']==v['venue_key']}
        for rr in data['races']:
            known={h['number']:h['name'] for h in races[rr['race']]['horses']}
            if any(row['number'] not in known or row['name'].replace(' ','')!=known[row['number']].replace(' ','') for row in rr['rows']):raise ValueError('Result runner mismatch')
        results[v['venue_key']]=data
    path.with_suffix('.html').write_text(render(d,path.name,results),encoding='utf-8')
