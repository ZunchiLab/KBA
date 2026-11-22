"""Shared compact JRA/NAR layout, with authority-specific data adapters."""
from pathlib import Path
from html import escape
import json
from render_day_prediction import comparison_table, formation_section, past_item, result_for, finish
from jra_payouts import payout_html

ROOT=Path(__file__).resolve().parents[1]
E=lambda x:escape(str(x),quote=True)
safe=lambda x:json.dumps(x,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')

def price_eligible(p):
    flags=[t.get("price_condition_at_snapshot") is True for t in p["tickets"]]
    return any(flags) if p.get("price_rule")=="individual" else all(flags)

def brief_plan(p):
    separator=' → ' if p.get('ordered') else ' − '
    if p['method']=='formation':
        return separator.join(','.join(map(str,g)) for g in p['groups'])
    return ' / '.join(('→' if p.get('ordered') else '−').join(map(str,t['numbers'])) for t in p['tickets'])

def plan_html(p,visible=False,guide=''):
    floors=sorted(set(t['minimum_odds'] for t in p['tickets']))
    floor=' / '.join(f'{x:.1f}' for x in floors)
    count=sum(t['price_condition_at_snapshot'] is True for t in p['tickets'])
    individual=p.get('price_rule')=='individual'
    ok=price_eligible(p)
    condition_label='各点下限' if individual else '全点'
    condition_text=('各点の価格条件を個別に適用。未達の点は購入しません。' if individual else '全点が下限以上。1点でも未達なら案全体を見送りします。')
    label=('購入候補・'+p['priority'] if p.get('priority') else '本線') if p['selected_for_example'] else '入替え案' if p['role']=='alternative' else '参考・本線見送り'
    out=[f'<section class="bet-plan" data-plan="{E(p["plan_id"])}"><div class="row"><h3>{label} · {E(p["type"])}</h3><button class="copy-plan" data-plan-id="{E(p["plan_id"])}" type="button">コピー</button></div>',
         guide or f'<p class="formation"><b>{E(brief_plan(p))}</b></p>',
         f'<p class="plan-meta">{p["points"]}点 × 100円 = <b>{p["maximum_example_yen"]:,}円例</b> · {condition_label}{floor}倍以上</p>',
         f'<p class="price-status {"ok" if ok else "wait"}">保存価格 {count}/{p["points"]}点達成 · {"直前確認で判断" if ok else "価格未取得・発売後に判定" if any(t.get("price_condition_at_snapshot") is None for t in p["tickets"]) else "この案は見送り"}</p>']
    # Keep the full individual tickets, saved prices and timestamps reviewable.
    rows=[]
    for t in p['tickets']:
        rows.append('<tr><th>'+E(('→' if p.get('ordered') else '−').join(map(str,t['numbers'])))+'</th><td>'+E(t['price']['raw'])+'</td><td>'+f'{t["minimum_odds"]:.1f}'+'</td></tr>')
    table='<table class="tickets"><thead><tr><th>買い目</th><th>保存倍率</th><th>下限</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table>'
    out.append('<details><summary>保存価格・全'+str(p['points'])+'点</summary>'+table+'</details>')
    source=p['tickets'][0]['source'];token=source.get('request_fields',{}).get('cname')
    market=(f'<form class="official-market" action="{E(source["url"])}" method="post" target="_blank"><input type="hidden" name="cname" value="{E(token)}"><button type="submit">公式オッズ</button></form>' if token else f'<a href="{E(source["url"])}">公式オッズ</a>')
    out.append('<details class="plan-conditions"><summary>購入条件・確認時刻</summary><p>'+E(p['reason'])+'</p><p>'+E(p['tickets'][0]['snapshot_label'])+'／取得 '+E(source['retrieved_at'])+'</p><p>取消なし・馬場と当日状態を確認・締切前。'+E(condition_text)+' 未確認なら購入を保留。金額は例、実購入未記録。</p><p>'+E(p.get('one_hit_at_floor',''))+'</p>'+market+'</details>')
    out.append(f'<p class="plan-result" data-plan-result="{E(p["plan_id"])}">結果待ち · 実購入未記録</p></section>')
    return ''.join(out)

def purchase_guide(race, plan):
    """Use the published tickets to identify each horse's role on the card."""
    horses={h['number']:h['name'] for h in race['horses']}
    pool=set().union(*(set(t['numbers']) for t in plan['tickets']))
    common=set.intersection(*(set(t['numbers']) for t in plan['tickets']))
    axes=(set(plan['groups'][0]) if plan['method']=='formation' else common) if plan['points']>1 else set()
    if plan['kind']=='quinella':
        goal='この2頭が1・2着。順番は自由。'
    elif plan['kind']=='wide':
        goal='この2頭がともに3着以内。順番は自由。'
    else:
        goal='この3頭が全て3着以内。順番は自由。'
    role=lambda n:('軸候補' if plan['kind']=='quinella' else '軸') if n in axes else '相手' if axes else '買い目'
    numbers=sorted(pool,key=lambda n:(n not in axes,next(h['rank'] or 999 for h in race['horses'] if h['number']==n)))
    labels=''.join(f'<li><small>{role(n)}</small> <b>{n} {E(horses[n])}</b></li>' for n in numbers)
    combos=' / '.join('–'.join(map(str,t['numbers'])) for t in plan['tickets'])
    prices=''
    if plan['points']<=2:
        prices='<p>保存オッズ '+E(' / '.join(t['price']['raw']+'倍' if t['price']['lower'] is not None else '未取得' for t in plan['tickets']))+'</p>'
    why=race['analysis'].get('buy_summary',race['analysis']['headline'])
    return f'<div class="buy-guide"><p class="formation"><b>{E(combos)}</b></p><ul>{labels}</ul><p>{E(goal)}</p><p>{E(why)}</p>{prices}</div>',{n:role(n) for n in pool}

def order_panel(race):
    order = race['analysis']['purchase_order']
    if order['mode']=='market':
        return '<aside class="order-panel"><b>新馬は買い順を保留</b><p>全頭を朝の単勝順で掲載。馬名を開くと、父・厩舎・騎手の関連実績を確認できます。</p></aside>'
    horses={h['number']:h for h in race['horses']}
    numbers=order['first_seven']
    partner=order.get('partner_end',4)
    cover=order.get('cover_end',7)
    marked=set(race['analysis'].get('mark_selection',{}).get('marked_numbers',numbers))
    rows=[]
    for label,group in [('1番手・軸',numbers[:1]),(f'2〜{partner}番手・相手',numbers[1:partner]),(f'{partner+1}〜{cover}番手・補完',numbers[partner:cover])]:
        group=[n for n in group if n in marked]
        if not group:continue
        labels='、'.join(str(n)+' '+horses[n]['name'] if len(group)==1 else str(n) for n in group)
        rows.append('<div><dt>'+E(label)+'</dt><dd>'+E(labels)+'</dd></div>')
    title='障害の参考順' if order['mode']=='hurdle' else '買う順番'
    comparison=''
    if len(numbers)>=2:
        first,second=(horses[n] for n in numbers[:2])
        values=[]
        for key,label in [('top2','連対'),('top3','3着内')]:
            v1=first['role_indices'][key]['value']
            v2=second['role_indices'][key]['value']
            if v1 is not None and v2 is not None:
                values.append(f'{label} {v1:.1f} / {v2:.1f}（差{abs(v1-v2):.1f}）')
        if values:
            comparison='<p>実績値 '+str(numbers[0])+'番 / '+str(numbers[1])+'番　'+E('、'.join(values))+'。差は得点単位です。</p>'
    return ('<section class="order-panel"><h3>'+title+'</h3><dl>'+''.join(rows)+'</dl>'
            '<details><summary>軸と相手をこの順にした理由</summary><p>'+E(order['axis_reason'])+'</p><p>'+
            E(order['partners_reason'])+'</p>'+comparison+'<p><b>外れる展開</b> '+E(order['risk'])+'</p></details></section>')


def price_comparison(race):
    checks=race['analysis'].get('preflight_review',{}).get('same_cost_price_comparisons',[])
    if not checks:return ''
    kinds={'quinella':'馬連','wide':'ワイド','trio':'三連複'}
    def line(entry):
        raw=entry['price']
        odds=raw['raw']+'倍' if raw['lower'] is not None else '取得なし'
        floor=' / 下限'+str(entry['minimum_odds'])+'倍' if 'minimum_odds' in entry else ''
        return E(kinds[entry['kind']]+' '+'–'.join(map(str,entry['numbers']))+' '+odds+floor+'（'+entry['checked_at'][11:19]+' JST）')
    return ('<details class="analysis"><summary>同額の別の買い方と比較</summary>'+
            ''.join('<p>採用案 '+line(c['retained'])+'<br>比較案 '+line(c['alternative'])+
                    '</p><p>各'+str(c['cost_yen'])+'円例。'+E(c['rationale'])+'</p>' for c in checks)+'</details>')


def card_only(race, result):
    result=result or {}
    uid=race['race_uid']
    search=' '.join([race['name']]+[h['name'] for h in race['horses']])
    rows=''.join(f'<details class="horse" data-number="{h["number"]}"><summary><span class="mark">–</span><span class="horse-label"><b>{h["number"]} {E(h["name"])}</b></span><span></span><strong class="horse-finish">{E(finish(result,h))}</strong></summary></details>' for h in race['horses'])
    return (f'<article class="race" id="{uid}" data-venue="{race["venue_key"]}" data-start="{E(race["start_at"])}" data-search="{E(search)}" data-bets="false">'
            f'<header class="race-head"><div class="row"><b>{E(race["venue"])} {race["race"]}R · {E(race["start"])}</b><span class="decision-badge skip">予想対象外</span></div><h2>{E(race["name"])}</h2><p class="clock-state"></p></header>'
            f'<div class="race-body"><p>{E(race["reason"])}</p><div class="payouts">{payout_html(result)}</div><h3>出走馬と結果</h3><p class="race-result-status">{E(result.get("note","結果待ち"))}</p><div class="all-horses">{rows}</div><p><a href="{E(race["source"]["url"])}">JRA公式出馬表</a></p></div></article>')

def render(d,json_name,results):
    authority=d.get('authority','jra');authority_label='地方' if authority=='nar' else 'JRA'
    buy_first=authority=='jra' and d.get('presentation',{}).get('buy_first',False)
    index_guide=buy_first and d.get('presentation',{}).get('index_guide',False)
    order_view=buy_first and d.get('presentation',{}).get('purchase_order',False)
    excluded=[r for r in d.get('excluded_races',[]) if r.get('card_only')]
    all_races=d['races']+excluded
    b=d['budget'];n=sum(len(r['horses']) for r in d['races']);selected=[r for r in d['races'] if any(p['selected_for_example'] for p in r['bet_plans'])]
    withdrawn=sum(h['status_at_snapshot']=='withdrawn' for r in d['races'] for h in r['horses'])
    count_note=f'（出走予定{n-withdrawn}・取消{withdrawn}）' if withdrawn else ''
    eligible=[r for r in selected if all(price_eligible(p) for p in r['bet_plans'] if p['selected_for_example'])]
    price_defaults=d.get('presentation',{}).get('price_eligible_defaults',False)
    default_cost=b['price_eligible_main_yen'] if price_defaults else b['selected_main_yen']
    css=(ROOT/'assets/css/jra-compact.css').read_text(encoding='utf-8')
    scope=(f'全{len(all_races)}R・{n+sum(len(r["horses"]) for r in excluded)}頭掲載 / 予想{len(d["races"])}R' if excluded else f'全{len(d["races"])}R / {n}頭{count_note}')
    parts=[f'<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#173b34"><title>{E(d["date_jst"])} {authority_label} 本気予想</title><style>{css}</style></head><body class="compact"><main>',
           f'<header class="hero"><div class="row"><h1>{E(d["date_jst"][5:].replace("-","/"))} {authority_label} 本気予想</h1><a href="../index.html">一覧</a></div><p>{E("・".join(v["label"] for v in d["venues"]))} · {scope} · {E(d["fixed_at"][11:16])} JST固定</p></header>',
           '<nav class="sticky" aria-label="競馬場とレース"><div id="venue-tabs" role="tablist">'+''.join(f'<button role="tab" type="button" id="tab-{v["venue_key"]}" aria-controls="venue-{v["venue_key"]}" aria-selected="false" data-venue="{v["venue_key"]}">{E(v["label"])}</button>' for v in d['venues'])+'</div>']
    for v in d['venues']:
        parts.append(f'<div class="race-jumps" data-venue="{v["venue_key"]}" aria-label="{E(v["label"])}レース番号">'+''.join(f'<a href="#{r["race_uid"]}" data-race-uid="{r["race_uid"]}">{r["race"]}</a>' for r in sorted(all_races,key=lambda r:r['race']) if r['venue_key']==v['venue_key'])+'</div>')
    parts.append('<div class="filters"><input id="horse-search" type="search" aria-label="馬名・レース検索" placeholder="馬名・レース検索"><select id="race-filter" aria-label="レース表示"><option value="all">全レース</option><option value="buy">本線候補</option><option value="future">発走前</option></select></div></nav>')
    if buy_first:
        featured=[r for r in eligible if r['analysis'].get('priority')=='優先']
        if featured:
            parts.append('<section class="featured-picks" aria-label="まず見る買い目"><h2>まず見る買い目</h2><div>')
            for r in sorted(featured,key=lambda r:r['start_at']):
                p=next(p for p in r['bet_plans'] if p['selected_for_example'])
                combos=' / '.join('–'.join(map(str,t['numbers'])) for t in p['tickets'])
                parts.append(f'<a href="#{r["race_uid"]}" data-featured-start="{E(r["start_at"])}"><b>{E(r["venue"])}{r["race"]}R</b> {E(p["type"])} {E(combos)} </a>')
            parts.append('</div></section>')
    summary=f'価格達成{len(eligible)}R · {b["price_eligible_main_yen"]:,}円例 / 候補{len(selected)}R' if price_defaults else '本線'+str(len(selected))+'R · 全点 '+f'{b["selected_main_yen"]:,}'+'円例'
    parts.append('<section class="day-summary"><details><summary>'+summary+' <span>一覧・予算</span></summary><div class="quick-picks">')
    for r in selected:
        p=next(p for p in r['bet_plans'] if p['selected_for_example'])
        status=(' · 価格未取得・購入保留' if any(t.get('price_condition_at_snapshot') is None for t in p['tickets']) else ' · 価格未達・全点見送り' if not price_eligible(p) else ' · 直前確認で判断') if price_defaults else ''
        parts.append(f'<a href="#{r["race_uid"]}"><b>{E(r["venue"])}{r["race"]}R</b> {E(r["start"])} · {E(p["type"])}<br>{E(brief_plan(p))} · {p["maximum_example_yen"]:,}円{status}</a>')
    parts.append(f'</div><p>各100円の例。上限例{b["day_limit_yen"]:,}円／保存価格条件達成分{b["price_eligible_main_yen"]:,}円。直前条件は未確認。余りは再配分しません。</p><div id="plan-total" role="status">仮プラン {default_cost:,}円</div><a href="../tools/bet-planner.html">購入記録の補助</a></details></section>')
    if order_view:
        audit=d.get('order_objectives_baseline',{})
        diag=''
        if audit.get('races'):
            items=[('◎の連対','axis_top2'),('◎の3着内','axis_top3'),('2〜4番手から1頭以上','partner_2_4'),
                   ('7番手までで全頭捕捉','cover_7'),('3条件すべて','joint'),('馬連フォーメーション','quinella'),('三連複フォーメーション','trio')]
            rows=''.join('<tr><th>'+label+'</th><td>'+str(audit['summary']['rank'][k])+'</td><td>'+str(audit['summary']['market'][k])+'</td></tr>' for label,k in items)
            diag='<p>過去'+str(len(audit['dates']))+'開催日・既走平地'+str(audit['races'])+'Rの該当レース数。市場基準は同じ保存時点の単勝順です。</p><table class="tickets"><thead><tr><th>検証項目</th><th>印順</th><th>市場順</th></tr></thead><tbody>'+rows+'</tbody></table>'
            if audit.get('field_bands'):
                band_rows=''.join(f"<tr><th>{b['lo']}〜{b['hi']}頭</th><td>{b['races']}</td><td>{b['sized']['rank']['axis_top2']}</td><td>{b['sized']['rank']['cover_7']} / {b['fixed']['rank']['cover_7']}</td></tr>" for b in audit['field_bands'])
                diag+='<details><summary>頭数別で絞った場合</summary><table class="tickets"><tr><th>頭数</th><th>R数</th><th>◎連対</th><th>全頭捕捉 縮小案 / 7頭</th></tr>'+band_rows+'</table><p>同じ発走前の印順での事後比較。新しい軸選定の成績は今後検証します。</p></details>'
            slots=audit.get('by_slot',{}).get('rank',[])
            if slots:
                slot_rows=''.join('<tr><th>'+str(s['slot'])+'番手</th><td>'+str(s['top2'])+'/'+str(s['races'])+'</td><td>'+str(s['top3'])+'/'+str(s['races'])+'</td></tr>' for s in slots)
                diag+='<details><summary>1〜7番手を個別に見る</summary><table class="tickets"><thead><tr><th>印順</th><th>連対</th><th>3着内</th></tr></thead><tbody>'+slot_rows+'</tbody></table></details>'
        parts.append('<details class="day-summary"><summary><b>印順で買った過去成績・指標の読み方</b></summary>'+diag+
                     '<p>◎は連対と3着内の軸。16頭以上は相手4番手・補完7番手まで。13〜15頭は4・6、10〜12頭は3・5、9頭以下は3・4を目安に印と点数を選びます。上の全体比較は従来の4・7固定です。全頭欄の連対・3着内の順位は役割別の実績値から計算し、同点は同順位です。役割値の小差は小さいまま表示します。新馬は参考欄に分けています。</p></details>')
    elif index_guide:
        benchmark=d.get('historical_rank_comparison')
        diagnostic=''
        if benchmark:
            counts=benchmark['top5_all']
            diagnostic=(f'<p>過去の固定予想 {benchmark["races"]}Rで、上位5頭に馬券内の全馬が入った回数は、印順{counts["予想印順"]}回、3着内指標{counts["3着内指標"]}回、旧圏内比較{counts["旧圏内比較"]}回。全項目が揃った既走平地での集計です。</p>')
        parts.append('<details class="day-summary index-reading"><summary><b>買う組は本線から</b>　印と指標の読み方</summary>'
                     '<p><b>買う組を選ぶ</b>　各レースの本線に、券種・馬番・馬名・必要オッズを表示します。見送りも予想の結論です。</p>'
                     '<p><b>相手を比べる</b>　印は距離・クラス・展開まで考えた予想順。馬連は「連対」、ワイド・三連複は「3着内」の指標で実績を見比べられます。</p>'
                     '<p><b>旧「圏内比較」</b>　直近4走までの着順を重く見た旧総合指数の内訳です。4役割は最大8走を使い、同じレース内で50を基準に比べます。55点は55％を意味しません。</p>'+diagnostic+'</details>')
    elif d.get('presentation',{}).get('day_notice'):
        parts.append('<p class="day-summary">'+E(d['presentation']['day_notice'])+'</p>')
    parts.append('<section class="result-toolbar" id="results-panel"><button id="refresh-results" type="button">結果を更新</button><details><summary>取得状況</summary><p id="result-status" role="status" aria-live="polite">'+E('保存結果を表示' if results else '発走前・結果未取得')+'</p></details></section><p id="empty-state" hidden>該当レースなし</p>')
    for v in d['venues']:
        key=v['venue_key'];vr=sorted((r for r in all_races if r['venue_key']==key),key=lambda r:r['race'])
        parts.append(f'<section class="venue-panel" id="venue-{key}" role="tabpanel" aria-labelledby="tab-{key}">')
        for r in vr:
            if r.get('card_only'):
                parts.append(card_only(r,result_for(results,key,r['race'])))
                continue
            uid=r['race_uid'];a=r['analysis'];res=result_for(results,key,r['race']);main=[p for p in r['bet_plans'] if p['selected_for_example']]
            search=' '.join([r['name'],str(r['race'])+'R']+[h['name'] for h in r['horses']])
            confidence=a['confidence'].replace('（主観）','');decision=(a.get('priority','条件付き本線')+'候補' if a.get('priority') else '条件付き本線') if main else '見送り'
            main_ready=bool(main and all(price_eligible(p) for p in main))
            if buy_first: decision=('買うならこの組' if main_ready else 'オッズ条件で見送り' if main else '見送り')
            surface={'turf':'芝','dirt':'ダ','hurdle':'障'}[r['surface']]
            going=r['going'].replace('ダート','').replace('芝','').replace('：','').strip()
            level=r['grade'] or r['class_text']
            actionable=main_ready if buy_first else bool(main)
            race_class='race buy-first' if buy_first else 'race'
            parts.append(f'<article class="{race_class}" id="{uid}" data-venue="{key}" data-start="{E(r["start_at"])}" data-search="{E(search)}" data-bets="{str(actionable).lower()}"><header class="race-head"><div class="row"><b>{E(v["label"])} {r["race"]}R · {E(r["start"])}</b><span class="decision-badge {"buy" if actionable else "skip"}">{decision}</span></div><h2>{E(r["name"])}</h2><p>{E(level)} · {surface}{r["distance_m"]}m · {E(going)} · {len(r["horses"])}頭 <span class="clock-state"></span></p><div class="badges"><span>自信 {E(confidence)}</span><span>波乱 {E(a["volatility"])}</span><small>主観評価</small></div></header><div class="race-body">')
            secondary=[]
            parts.append('<div class="payouts">'+payout_html(res)+'</div>')
            if order_view:
                parts.append(order_panel(r))
                secondary.append(price_comparison(r))
            if not main and not buy_first:parts.append('<p class="one-line">'+E(a['headline'])+'</p>')
            buy_roles={}
            for p in main:
                if buy_first:
                    guide,buy_roles=purchase_guide(r,p)
                else:guide=''
                parts.append(plan_html(p,True,guide=guide))
            if not main:parts.append('<p class="skip-reason">'+E(a.get('short_skip',a['decision']))+'</p>')
            secondary.append('<details class="analysis"><summary>展開・軸・除外理由</summary><p>'+E(a['headline'])+'</p><p><b>勝つ候補</b> '+E(a['win_view'])+'</p><p><b>圏内候補</b> '+E(a['place_view'])+'</p><p><b>主展開</b> '+E(a['pace'])+'</p><p><b>別展開</b> '+E(a['alternate'])+'</p><p>'+E(a['decision'])+'</p><p>'+E(a['popular_compare'])+'</p><p>荒れ確率は未算定。比較指数・自信度は確率ではありません。</p></details>')
            other=[p for p in r['bet_plans'] if not p['selected_for_example']]
            if other:secondary.append('<details class="other-plans"><summary>'+('入替え案' if main else '参考の買い目')+'</summary>'+''.join(plan_html(p) for p in other)+'</details>')
            if r['bet_plans']:
                default_main=[p for p in main if not price_defaults or price_eligible(p)]
                secondary.append(f'<details class="plan-controls"><summary>仮プランを変更</summary><fieldset class="plan-choice"><legend>費用例の選択・購入ではありません</legend><label><input type="radio" name="{uid}" value="skip" data-cost="0" {"checked" if not default_main else ""}>見送り</label>')
                for p in r['bet_plans']:secondary.append(f'<label><input type="radio" name="{uid}" value="{p["plan_id"]}" data-cost="{p.get("price_eligible_example_yen",p["maximum_example_yen"]) if price_defaults and p in default_main else p["maximum_example_yen"]}" {"checked" if p in default_main else ""}>{E(p["type"])} {p["maximum_example_yen"]:,}円例</label>')
                secondary.append('</fieldset></details>')
            market_reference=authority=='jra' and all(h.get('score_method')=='market_reference' for h in r['horses'])
            horse_heading='全頭の市場参考（能力指数ではありません）' if market_reference else '全頭の総合印・近走指数'
            marks=a.get('mark_selection')
            if marks:
                count=len(marks.get('marked_numbers',[]))
                horse_heading+=f'（印{count}頭）'
                reviews=''.join('<p>'+E(str(e['number'])+'と'+ '・'.join(map(str,e.get('compared_with',[])))+'の比較：'+e.get('reason',''))+'</p>' for e in marks.get('boundary_reviews',[]))
                exception='<p><b>目安を超える理由：</b>'+E(marks['exception_reason'])+'</p>' if marks.get('exception_reason') else ''
                coverage=marks.get('coverage_review',{})
                coverage_html=''
                limit_note='頭まで。枠を埋めず比較して選定。'
                if marks.get('policy')=='coverage-first-v2':
                    limit_note='頭を参考に、3頭捕捉を優先。購入点数とは分離。'
                    role_labels={'first':'1着','second':'2着ちょうど','top2':'連対','top3':'3着内'}
                    coverage_html=''.join('<p>'+role_labels.get(k,k)+'候補：'+E('・'.join(map(str,v)))+'</p>' for k,v in coverage.get('candidate_groups',{}).items())
                    coverage_html+=''.join('<p>'+E(s['name'])+'：'+E('・'.join(map(str,s['numbers'])))+' / '+E(s['reason'])+'</p>' for s in coverage.get('scenario_groups',[]))
                secondary.append('<details class="mark-selection"><summary>印'+str(count)+'頭の選定理由</summary><p>出走予定'+str(marks['field_size_at_review'])+'頭 / 印の目安'+str(marks['suggested_limit'])+limit_note+'</p><p>'+E(marks['reason'])+'</p>'+exception+coverage_html+reviews+'<p>確認 '+E(marks['reviewed_at'])+'。印数の目安は的中確率や最適頭数の推定ではありません。全頭の順位・指数は保持。</p></details>')
            role_view=authority=='jra' and any(h.get('role_indices') for h in r['horses'])
            if role_view:
                debut_view=any(h.get('role_indices',{}).get('method')=='debut_cohort_reference' for h in r['horses'])
                if debut_view:horse_heading=horse_heading.replace('全頭の市場参考（能力指数ではありません）','全頭の新馬参考（関連実績）')
                options=[('rank','総合印順'),('number','馬番順'),('score','旧総合指数順'),('first','1着指数順'),('second','2着ちょうど指数順'),('top2','連対指数順'),('top3','3着内指数順'),('market','保存単勝人気順')]
                if debut_view:options[0]=('rank','参考順位（保存単勝順）')
                if index_guide:
                    options[0]=('rank','保存人気順（新馬）' if debut_view else '予想順（印）')
                    options[2]=('score','旧指数順（参考）')
                    options[5]=('top2','連対順（馬連）')
                    options[6]=('top3','3着内順（ワイド・三連複）')
                control='<select class="horse-sort" aria-label="指標の並べ替え">'+''.join('<option value="'+k+'">'+v+'</option>' for k,v in options)+'</select>'
                labels='<span class="role-scores"><span>1着</span><span>2着</span><span>連対</span><span>3着内</span></span>'
                relative_view=any(h.get('role_indices',{}).get('version')=='jra-role-relative-v2' for h in r['horses'])
                legend='同一レース・同一役割の相対実績比較（基準50）。確率ではありません。2着＝ちょうど2着、連対＝2着以内。参考と資料量は馬名の下に表示。' if relative_view else '2着＝ちょうど2着、連対＝2着以内。0〜100の実績比較・確率ではありません。~は条件替わり等の参考。'
                if debut_view:legend='新馬は父・厩舎・騎手の関連実績参考（基準50）。本人の実走評価・確率ではありません。2着＝ちょうど2着、連対＝2着以内。調教は未採点。'
                toggle='<label class="index-control"><input type="checkbox" class="show-indices">4指標を表示</label>' if buy_first else ''
                if buy_first:
                    horse_heading='全頭の印と評価'
                    legend='同じレース内で高いほど上位、基準は50。馬連は「連対（2着以内）」、ワイド・三連複は「3着内」が目安。2着はちょうど2着。新馬は父・厩舎・騎手の関連実績。' if debut_view else '同じレース内で高いほど上位、基準は50。馬連は「連対（2着以内）」、ワイド・三連複は「3着内」が目安。2着はちょうど2着。着順の確率とは別の実績比較です。'
                if index_guide:
                    legend=('新馬は父・厩舎・騎手の関連実績。本人の実走は0走。' if debut_view else '馬連は連対、ワイド・三連複は3着内。')+' 同じレース内で50が基準。55点は55％を意味しません。'
                if order_view:
                    horse_heading='全頭の買い順' if a['purchase_order']['mode']=='purchase' else '全頭の参考順'
                    legend='馬名を開くと順位の理由が読めます。' + (' 新馬の実績順位は父・厩舎・騎手の参考。' if debut_view else ' 連対・3着内は実績順位。同点は同順位。')
                parts.append('<div class="row horse-toolbar role-toolbar"><h3>'+horse_heading.replace('近走指数','役割別指数')+'</h3>'+control+toggle+'</div><p class="role-legend">'+E(legend)+'</p><p class="race-result-status">'+E(res.get('note','結果待ち') if res else '結果待ち')+'</p><div class="horse-columns role-columns"><span>印 / 馬番・馬名</span>'+labels+'<span>着順</span></div><div class="all-horses role-horses">')
            else:
                parts.append('<div class="row horse-toolbar"><h3>'+horse_heading+'</h3><button class="sort-horses" type="button">馬番順</button></div><p class="race-result-status">'+E(res.get('note','結果待ち') if res else '結果待ち')+'</p><div class="horse-columns"><span>印 / 馬番・馬名</span><span>'+('市場参考' if market_reference else '指数')+'</span><span>着順</span></div><div class="all-horses">')
            if a.get('index_note'):
                parts.insert(len(parts)-1,'<p class="index-note">'+E(a['index_note'])+'</p>')
            for h in sorted(r['horses'],key=lambda h:h['rank'] or 999):
                score=h['score'] if h['score'] is not None else '未算出' if authority=='nar' else '保留';mark=h['mark'].replace('参考','').replace('暫定','');f=finish(res,h)
                if f in ['保存時は発走前','未確定','全着順待ち']:f='—'
                score_class='score pending' if h['score'] is None else 'score'
                ref_label=h.get('score_label','能力指数') if authority=='nar' else '市場参考' if h['score_method']=='market_reference' else '暫定比較' if r['surface']=='hurdle' else ('近走実績指数' if d.get('presentation',{}).get('detailed_rank_labels') else '比較指数')
                rank_label=str(h['rank'])+'位' if h['rank'] is not None else '取消' if h['status_at_snapshot']=='withdrawn' else '順位保留'
                if d.get('presentation',{}).get('detailed_rank_labels'):
                    rank_label=('市場参考'+rank_label if market_reference else '総合'+('暫定' if '暫定' in h['mark'] or r['surface']=='hurdle' else '')+rank_label+(' / 指数未算出' if authority=='nar' and h['score'] is None else ' / 指数'+(str(h['model_rank'])+'位' if h.get('model_rank') else '保留')))
                history=h.get('history_audit');history_html=''
                if history:
                    history_html='<details><summary>公式掲載戦歴の確認範囲</summary><p>'+E(history.get('summary',history.get('scope','確認範囲は原文を参照')))+'</p><a href="'+E(history['source']['url'])+'">' +authority_label+'公式掲載履歴</a><p>確認 '+E(history['source']['retrieved_at'])+'。掲載範囲外の経験は断定しません。</p></details>'
                attrs='';role_detail='';score_html=f'<b class="{score_class}">{E(score)}</b>'
                if role_view:
                    indices=h.get('role_indices',{});method=indices.get('method');ref=method in ['cross_surface_reference','market_reference','debut_cohort_reference'] or r['surface']=='hurdle'
                    cells=[]
                    for role in ['first','second','top2','top3']:
                        value=indices.get(role,{}).get('value');attrs+=' data-'+role+'="'+(str(value) if value is not None else '')+'"'
                        cells.append('<b title="'+E(indices.get(role,{}).get('label',role))+'">'+E(('~' if ref and not relative_view else '')+str(value) if value is not None else '—')+'</b>')
                    attrs+=' data-rank="'+str(h['rank'] or '')+'" data-score="'+str(h['score'] if h['score'] is not None else '')+'" data-inactive="'+str(h['status_at_snapshot'] in ['withdrawn','excluded']).lower()+'"'
                    attrs+=' data-market="'+str(h.get('market',{}).get('win') or '')+'"'
                    score_html='<span class="role-scores">'+''.join(cells)+'</span>'
                    rank_label='総合'+(str(h['rank'])+'位' if h['rank'] else '対象外')+' / '+indices.get('label','未算出')
                    if method=='debut_cohort_reference' and h.get('score_method')=='market_reference':rank_label='朝単勝'+(str(h['rank'])+'番手' if h['rank'] else '対象外')+' / '+indices.get('label','未算出')
                    if relative_view:
                        runs=indices.get('runs',0);rank_label+=' / '+('関連'+str(indices['matched_starters'])+'例・薄' if method=='debut_cohort_reference' else '採点'+str(runs)+'走・'+indices.get('confidence','未評価'))
                        if h.get('pop'):rank_label+=' / 朝単勝順'+str(h['pop'])
                        if indices.get('market_reference'):rank_label+=' / 保存単勝'+str(indices['market_reference']['value'])+'倍'
                    refs=''.join('<li><a href="'+E(url)+'">根拠走 '+str(i+1)+'</a></li>' for i,url in enumerate(indices.get('source_refs',[])))
                    index_rule='<p>50は今回の比較基準。資料が少ない・古い場合は極端な評価を抑えます。レースをまたぐ絶対能力や着順確率ではありません。市場値は4指標にコピーしません。</p>' if relative_view else ''
                    role_detail='<details class="role-method"><summary>4指標の根拠・資料の強さ</summary><p>'+E(indices.get('reason','未算出'))+'</p><p>材料の充足度 '+E(indices.get('confidence','未評価'))+' / 実走 '+E(indices.get('runs',0))+'走。推定手順は未学習・未校正。</p><p>1着は着差重視、2着は過去着順と2着の近さ、連対・3着内は各範囲への実績を別集約。新馬の4指標は空欄、市場参考は能力指数と分離。</p>'+index_rule+'<ul>'+refs+'</ul></details>'
                    if method=='debut_cohort_reference':
                        sample_rows=''.join('<li>'+E(c['date'])+' '+E(c['name'])+' '+str(c['finish'])+'/'+str(c['field'])+'着 / 一致 '+E('・'.join({'sire':'父','trainer':'厩舎','jockey':'騎手'}[k] for k in c['matched_features']))+'</li>' for c in indices['components'])
                        role_detail='<details class="role-method"><summary>新馬4指標の根拠</summary><p>'+E(indices['reason'])+'</p><p>関連'+str(indices['matched_starters'])+'出走例。父40%・厩舎35%・騎手25%の一致を重みに使用し、同じ出走例は二重計上しません。各例の頭数に応じた基準との差を役割別に集計。未校正の参考値です。</p><p>調教は未採点。材料なしの50は能力を確認した値ではありません。朝の総合順位・印・買い目は変更しません。</p><ul>'+sample_rows+'</ul></details>'
                if index_guide and role_view:
                    role_detail=role_detail.replace('新馬の4指標は空欄、市場参考は能力指数と分離。','単勝人気は4指標から独立した市場の参考値です。')
                chip=f'<em class="ticket-horse">{E(buy_roles[h["number"]])}</em>' if main_ready and h['number'] in buy_roles else ''
                legacy_html=f'<p>{ref_label} {E(score)} · 勝比較 {E(h["win"] if h["win"] is not None else "未算定")} / 圏内比較 {E(h["place"] if h["place"] is not None else "未算定")}</p>'
                if index_guide:
                    if h.get('score_method')=='market_reference':
                        legacy_html=''
                    else:
                        legacy_html=('<details class="legacy-index"><summary>旧指数の内訳（参考）</summary>'
                                     f'<p>旧総合 {E(score)} ／ 着差重視 {E(h["win"] if h["win"] is not None else "未算定")} ／ 着順重視（旧・圏内比較） {E(h["place"] if h["place"] is not None else "未算定")}</p>'
                                     '<p>直近4走まで。着差を取得した走では着順70％・着差30％で旧「圏内比較」を計算し、クラスや距離も考慮します。現在の3着内指標とは別尺度です。</p></details>')
                judgment=h.get("mark_override_reason") or ("旧総合指数の順位を採用。4役割指標は別の参考評価です。" if role_view else "指数と総合順位が一致。以下の根拠と懸念を確認。")
                if index_guide and not h.get("mark_override_reason"):
                    judgment=('新馬の参考順位は保存した単勝オッズ順。' if market_reference else '今回の条件と展開を加味した予想順。採否は下の根拠と買い目に記載。')
                if order_view and h.get('purchase_order'):
                    order=h['purchase_order']
                    rank_label=(str(order['rank'])+'番手・'+order['tier']+' ｜ 連対 '+(str(order['top2'])+'位' if order['top2'] else '資料不足')+
                                ' / 3着内 '+(str(order['top3'])+'位' if order['top3'] else '資料不足'))
                    if order['disagreement']:rank_label+=' · 順位差の理由あり'
                    judgment=order['reason']
                parts.append(f'<details class="horse" data-number="{h["number"]}"{attrs}><summary><span class="mark">{E(mark)}</span><span class="horse-label"><b>{h["number"]} {E(h["name"])} {chip}</b><small>{E(rank_label)} · {E(h["style"])}</small></span>{score_html}<strong class="horse-finish">{E(f)}</strong></summary><div class="horse-detail"><p>{E(h["jockey"])} · {h["weight"]}kg · 馬体重 {E(h["body"] or "未発表")}</p>{legacy_html}<p><b>総合判断</b> {E(judgment)}</p><p><b>根拠</b> {E(h["reason"])}</p><p><b>懸念</b> {E(h["risk"])}</p><p><b>採否</b> {E(h["ticket_review"])}</p><details><summary>過去走と出典</summary><ul>'+''.join(past_item(p) for p in h['past'])+'</ul></details>'+history_html+role_detail+'</div></details>')
            parts.append('</div>'+''.join(secondary))
            parts.append(comparison_table(r)+formation_section(r))
            parts.append('<details class="sources"><summary>出馬表・確認時刻</summary><a href="'+E(r['source']['url'])+'">' +authority_label+'公式出馬表</a><p>出馬表 '+E(r['source']['retrieved_at'])+'／価格 '+E(r['source_checked_at'])+'</p><p>馬場は出馬表取得時点。取消・馬場・状態・価格は直前再確認。</p></details></div></article>')
        parts.append('</section>')
    # The browser only needs runner identity/rank, ticket plans and timestamps.
    races=[{k:r[k] for k in ['race_uid','venue_key','venue','race','start_at','bet_plans']}|{'horses':[{k:h[k] for k in ['number','name','rank','status_at_snapshot']} for h in r['horses']]} for r in all_races]
    config=dict(authority=authority,date=d['date_jst'],version=d['forecast_version'],jsonFile=json_name,venues=d['venues'],races=races,budget=b,compact=True,storageNamespace=d.get('presentation',{}).get('storage_namespace',''))
    if buy_first:config['buyFirst']=True
    digests={value.get('forecast_sha256') for value in results.values()}
    if len(digests)==1:config['forecastSha256']=next(iter(digests))
    extras=''.join('<p><a href="'+E(x['file'])+'">'+E(x['purpose'])+'</a></p>' for x in d.get('supplemental_files',[]))
    parts.append('<footer><details><summary>評価方法・未確認事項・JSON</summary><p>'+E(d['model']['definition'])+'</p><ul>'+''.join('<li>'+E(x)+'</li>' for x in d['model']['limitations'])+'</ul><p>自信・波乱は主観。荒れ確率は未校正のため未算定。事前予想は固定し、結果のみ別更新。</p><p>固定 '+E(d['fixed_at'])+' · '+E(d['forecast_version'])+'</p><a id="forecast-link" href="'+E(json_name)+'">全頭・買い目・比較記録JSON</a>'+extras+'</details><noscript>JavaScript無効時は全レースを表示します。</noscript></footer>')
    js=(ROOT/'assets/js/jra-day-report.js').read_text(encoding='utf-8')
    parts.append('<script type="application/json" id="day-forecast">'+safe(config)+'</script><script type="application/json" id="day-results">'+safe(results)+'</script><script>'+js+'</script></main></body></html>')
    return '\n'.join(parts)
