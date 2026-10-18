from pathlib import Path
from datetime import datetime,timezone,timedelta
from itertools import combinations
from copy import deepcopy
from html import escape
import json,hashlib,sys,shutil,re

ROOT=Path(__file__).resolve().parent;PROJECT=ROOT.parents[1]
REPO=Path(r'C:\Users\furokei\Documents\Codex\KBA')
SHARED=Path(r'C:\Users\furokei\Documents\Codex\2026-09-26\referenced-chatgpt-conversation-this-is-an')
OUT=PROJECT/'outputs/nar20261018_review';OUT.mkdir(parents=True,exist_ok=True)
NAME='report_20261018_nar_review_v1'
sys.path.insert(0,str(REPO/'scripts'))
from render_nar_compact import render
NOW=datetime.now(timezone(timedelta(hours=9))).isoformat(timespec='seconds')
f=json.loads((REPO/'predictions/report_20261018_nar_predictions_v1.json').read_text(encoding='utf-8-sig'))
o=json.loads((OUT/'official_verification.json').read_text(encoding='utf-8'))
official={r['venue_key']:r for r in o['results']}

NOTES={
'kochi':[
'結果は⑤→①→②。固定順位は2位・7位・4位。本線③⑤⑦BOXは⑤だけが圏内で全3点不的中、300円→0円。◎⑦は9着。軸を置かなかっただけでは、相手3頭の選択失敗を防げなかった。',
'⑤は6/28の当地1600mで2着0.1秒差、①は同じレースで3着0.2秒差。②はその同走では6着だが、9/22の1400mファイナル2着0.2秒差を保存済み。⑤①の同時好走の根拠と②の最新内容を買い目へ十分反映せず、古い同距離勝ちを持つ③⑦へ3枠を割いた。⑤を2位に置きながら勝つ候補7・3・8へ入れなかった役割判断も不足。',
'①は⑤より9/6の選抜で後れたため下げたが、それは①と⑤が同時に圏内へ来ない根拠にはならない。③は近5走圏外、⑦の近い1600mは5着。少額BOXでも「上位3頭をそのまま組む」判断では相手の同時好走を比較できていなかった。',
'同じ3点300円で③−⑤・⑤−⑦・②−⑤なら②−⑤が的中1,110円。元の③−⑦を②−⑤へ1点入替える診断で、予算増は不要だった。保存20:11価格も②−⑤は10.8〜11.6倍で元の下限3.5倍を満たす。ただし結果を知った後の例であり、事前の成績や未来の改善実証へ加算しない。',
'次回は⑤のような連対・圏内候補と、過去に同時好走した馬をセットで比較する。①②を③⑦と同じ級・距離・最新内容で比較し、BOXと軸流しの両方を同じ点数で検討する。近走不安を抱える候補ばかりなら、少額にしただけで購入理由が十分とは扱わない。'
],
'saga':[
'結果は③→⑭→⑥。本線③−⑭は的中150円、①−⑭は不的中。2点200円→150円で赤字。三連複別案は⑥を相手から除外し、600円→0円。◎⑭の圏内判断は合ったが、勝つ第一候補は2着で、相手①の圏内判断は14着と大きく外れた。',
'③の当地1400m連続2着と⑭の当地連勝は、2頭の同時好走を選ぶ根拠として機能した。一方、①の当地の圏内回数と近2走3着を安定性へ寄せすぎた。頭数・相手の変化・同型との競合は懸念に記載したが、採否や費用配分へ十分接続できなかった。実際の失速原因は当日通過順数値と映像がなく断定しない。',
'⑥を13位へ置いたのは反省点。発走前保存の公式履歴に、名古屋1500mの6/5・Ｂ１１組3着0.3秒差、5/25・Ｂ１５の3着0.5秒差があった。同場同距離だけを追加比較したため、この近似距離の内容を本文へ反映せず、初戦1300m9着3.4秒差と当地1400m未経験を重く扱った。級の名称を佐賀と同一評価にはできないが、未経験と能力不足を分ける作業を順位・相手枠で守れていなかった。',
'⑥は元の近5走だけなら強く推せる馬ではなく、追加履歴があっても必ず3着と選べたとは言えない。少なくとも13位・64点という差を能力差として示せる材料ではなかった。転入馬は他場の近似距離・級の原文と評価幅を保存し、相手候補外にする理由を確認する必要がある。',
'同じ別案6点600円なら、③⑭の2頭軸から①⑤⑥⑧⑨⑩へ流す構成で③−⑥−⑭が的中1,340円。ただし③⑭の両方が圏内に必要となり、元の1頭軸案とは失敗条件が違う。これも結果後の診断で、⑥を選べた未来の実証ではない。',
'本線の③−⑭だけなら100円→150円だが、これは費用を減らした診断。保存価格は2.2〜2.4倍から最終払戻1.5倍へ変化した。最終の表示オッズ・購入時刻は未取得で、下限2倍を満たして実行できたとは断定できない。結果に合わせて価格下限を下げない。'
]}

def settle(plan,result):
 labels={'wide':'ワイド','trio':'三連複','quinella':'馬連複'}
 pts=[]
 for t in plan['tickets']:
  money=sum(p['yen_per_100'] for p in result['refunds'] if p['kind']==labels[plan['kind']] and sorted(p['numbers'])==sorted(t['numbers']))
  pts.append(dict(t,hit=money>0,official_yen_per_100=money,payout_yen=money*t['example_stake_yen']//100))
 all_required=plan.get('price_rule')=='all_tickets_required'
 accepted=pts if (not all_required or all(t['price_condition_at_snapshot'] is True for t in pts)) else []
 if not all_required:accepted=[t for t in accepted if t['price_condition_at_snapshot'] is True]
 def total(ts):
  cost=sum(t['example_stake_yen'] for t in ts);paid=sum(t['payout_yen'] for t in ts)
  return dict(points=len(ts),cost_yen=cost,payout_yen=paid,net_yen=paid-cost,hit_points=sum(t['hit'] for t in ts),return_percent=round(paid/cost*100,2) if cost else None)
 return dict(original_plan=plan,tickets=pts,all_listed=total(pts),saved_price=total(accepted))

def counterfactual(v,title,kind,combos,minimum,why):
 prices=json.loads((PROJECT/f'work/nar20261018/{v}/prices.json').read_text(encoding='utf-8'))[kind+'11']
 ts=[]
 for c in combos:
  pr=prices['prices']['-'.join(map(str,sorted(c)))];ts.append(dict(numbers=sorted(c),example_stake_yen=100,price=pr,minimum_odds=minimum,price_condition_at_snapshot=pr['lower'] is not None and pr['lower']>=minimum))
 plan=dict(kind=kind,role='post_event_diagnostic',price_rule='all_tickets_required' if kind=='trio' else 'individual',tickets=ts)
 return dict(title=title,why=why,phase='post_event_diagnostic',blind=False,source=prices['source'],page_time_raw=prices['page_time_raw'],actual_purchase=None,settlement=settle(plan,official[v]))

races=[];totals={k:dict(cost_yen=0,payout_yen=0,points=0,hit_points=0) for k in ['main_all','main_price','rank_all','rank_price','popular_all','popular_price']};score_audit=[]
for r in f['races']:
 v=r['venue_key'];rr=official[v];fin={h['number']:h['finish'] for h in rr['rows']}
 plans=[settle(p,rr) for p in r['bet_plans']];baselines=[]
 for p,z in zip(r['bet_plans'],plans):
  if p['role']=='main':
   for k,a in [('main_all',z['all_listed']),('main_price',z['saved_price'])]:
    for field in totals[k]:totals[k][field]+=a[field]
  for b in r['analysis']['formation_review']['diagnostic_baselines']:
   if b['plan_id']!=p['plan_id']:continue
   s=settle(b,rr);s['method']=b['method'];baselines.append(s)
   if p['role']=='main':
    prefix='rank' if b['method']=='fixed_total_order' else 'popular'
    for suffix,a in [('all',s['all_listed']),('price',s['saved_price'])]:
     for field in totals[prefix+'_'+suffix]:totals[prefix+'_'+suffix][field]+=a[field]
 horses=[]
 for h in r['horses']:
  formula=90-2*h['rank'];score_audit.append(dict(race_uid=r['race_uid'],number=h['number'],rank=h['rank'],original_score=h['score'],formula_value=formula,equals_formula=h['score']==formula,definition=h['score_definition']))
  horses.append(dict(h,finish=fin[h['number']],official=next(x for x in rr['rows'] if x['number']==h['number'])))
 races.append(dict(race_uid=r['race_uid'],venue_key=v,venue=r['venue'],race=r['race'],name=r['name'],original_analysis=r['analysis'],horses=horses,rows=rr['rows'],refunds=rr['refunds'],source=rr['source'],plans=plans,baselines=baselines,notes=NOTES[v],actual_purchase=None))
for value in totals.values():value['net_yen']=value['payout_yen']-value['cost_yen'];value['return_percent']=round(value['payout_yen']/value['cost_yen']*100,2) if value['cost_yen'] else None
assert totals['main_price']['cost_yen']==500 and totals['main_price']['payout_yen']==150
assert len(score_audit)==25 and all(h['equals_formula'] for h in score_audit)
diagnostics=[counterfactual('kochi','1点だけを入替え、⑤と②の同時好走を残す','wide',[(3,5),(5,7),(2,5)],3.5,'元の③−⑦を②−⑤へ入替え。⑤の同距離2着と②の最新2着は事前保存済み。結果後の選択。'),counterfactual('saga','③⑭の2頭軸を比較する同費用例','trio',[(3,14,n) for n in [1,5,6,8,9,10]],7,'元の6点と同費用。未知の相手⑥まで残す代わりに③⑭の両方が圏内へ来る必要がある。結果後の選択。')]
assert diagnostics[0]['settlement']['all_listed']['payout_yen']==1110 and diagnostics[1]['settlement']['all_listed']['payout_yen']==1340
next_actions=[
'転入馬は同場同距離だけで打ち切らず、他場の同じダート・近似距離（目安±200m）の好走まで比較。級は原文を保持し、未検証の級換算を行わない。比較不能なら評価幅・順位保留と相手の採否を別表示する。',
'同じ過去走で先着した馬を上位に置くことと、後れた馬を相手から除くことを分ける。近い着差で同時好走した組合せを残した案と、現在のBOXを同じ点数で比較する。',
'同距離の勝ちがないだけで勝つ候補から外さず、今回の相手と先着可能性を比較する。勝ち候補・連対候補・圏内候補は総合順位と別に記録する。',
'強い2頭が同時に好走する根拠がある場合、ワイド1点・馬連・三連複2頭軸も比較する。必要着順・価格・費用・失敗条件が異なるため、自動的に買い方を切り替えない。',
'順位の等間隔変換を能力指数へ使わない。未算出はnullと理由。計算した指数は手法・根拠走・入力値・寄与を保存し、総合印と別表示する。今回の2Rへ合わせた係数調整は行わない。',
'次回地方HTMLはJRA共通のcompact-v1。1レース表示、追従タブと番号、本線、全頭の印・指数の有無・着順、先頭の全式別払戻、詳細の折畳み、結果保持とボタンの操作を揃える。'
]
d=dict(schema_version='kba.review/1',document_type='review',authority='nar',date_jst='2026-10-18',version='NAR-20261018-REVIEW-v1',venue='高知・佐賀',venues=f['venues'],phase='post_event_review',reviewed_at=NOW,forecast_sources=[dict(file='predictions/report_20261018_nar_predictions_v1.json',fixed_at=f['fixed_at'],version='v1',sha256=o['forecast_sha256'],hash_method='utf8-no-bom-lf-sha256')],actual_purchase=None,metrics=dict(races=2,horses=25,main_wins=0,main_top3=1,top3_podium_capture=3,podium_slots=6),settlements=totals,races=races,score_audit=dict(formula='90 - 2 * rank',matching_horses=25,total_horses=25,is_ability_index=False,items=score_audit),post_event_diagnostics=diagnostics,next_actions=next_actions,limitations=['掲載案の仮想検証。保存価格条件と直前の状態・価格・取消を満たして買った仮定。実購入は未確認。','当日通過順数値・映像は未確認。展開・体調を実際の敗因として断定しない。','結果後の組替えは盲検ではなく、当日の成績・未来日の改善実証へ加算しない。','地方と他場の級名の直接数値換算、指数モデルの採点・校正・未知日の改善は未実施。','表示と記録の修正は予測力の改善実証とは別。'])
history=json.loads((PROJECT/'work/nar20261018/history.json').read_text(encoding='utf-8'))
h6=next(x for x in history if x['venue']=='saga' and x['number']==6)
assert datetime.fromisoformat(h6['source']['retrieved_at'])<datetime.fromisoformat(f['fixed_at'])
d['additional_review_evidence']=[dict(venue_key='saga',number=6,source=h6['source'],available_before_forecast=True,used_in_original_comparison=False,scope='発走前取得の履歴中に存在したが、当地同距離の抽出では落とした近似距離実績。',runs=[dict(date=r[0],venue=r[1],race_name=r[3],distance_m=int(r[5]),finish=int(r[13]),margin_seconds=float(r[15]),source='https://www.keiba.go.jp/KeibaWeb/TodayRaceInfo/RaceMarkTable?k_raceDate='+r[0].replace('/','%2F')+'&k_raceNo='+str(int(r[2]))+'&k_babaCode=24') for r in h6['rows'] if r[0] in ['2026/06/05','2026/05/25']])]
(OUT/(NAME+'.json')).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
E=lambda s:escape(str(s),quote=True)
view=deepcopy(f);view['presentation']=dict(layout='compact-v1',default_race_mode='single',details_collapsed=True,storage_namespace='review')
result_data={v:json.loads((REPO/f'data/results/nar/2026-10-18/{v}.json').read_text(encoding='utf-8')) for v in ['kochi','saga']}
for v in result_data:
 result_data[v]['races']=[{k:official[v][k] for k in ['race','name','start_at','status','rows','refunds','source','note']}]
html=render(view,'report_20261018_nar_predictions_v1.json',result_data)
html=html.replace('2026-10-18 地方 本気予想','2026/10/18 高知・佐賀の反省').replace('10/18 地方 本気予想','10/18 高知・佐賀の反省')
intro='''<section class="review-intro" style="padding:12px;background:#fff5e6;border:1px solid #dcb980;border-radius:10px;margin:10px 0"><h2>開催後の反省</h2><p><b>本線5点500円 → 150円、−350円、回収30%。</b>各100円の掲載案の仮想精算。実購入未確認。</p><p>佐賀③−⑭の1点は的中したが全体で赤字。高知は相手選び、佐賀は転入馬の近似距離実績の反映不足。</p><p><b>指数の表示に問題がありました。</b>旧数値は全25頭が「90−2×順位」。能力指数ではありません。この画面では未算出と表示し、原本の数値はJSONへ保持します。</p><p>新しい画面は次回用のJRA共通レイアウト。今日の印・順位・理由・買い目・価格は発走前v1のまま。新しい事前予想ではありません。</p><p><a href="report_20261018_nar_review_v1.json">全頭の反省JSON</a> · <a href="report_20261018_nar_predictions_v1.html">固定予想と結果</a> · <a href="../tools/nar-compact-preview.html">複数レースの表示見本</a></p></section>'''
html=html.replace('</nav>','</nav>'+intro,1)
index=iter(races)
def inject(match):
 r=next(index);text='<section class="review-notes"><h3>'+E(r['venue'])+'11Rの反省</h3>'+''.join('<p>'+E(x)+'</p>' for x in r['notes'])+'</section>'
 return match.group(0)+text
html=re.sub(r'<div class="race-body">',inject,html)
summary='<details class="panel"><summary>次回に実行すること・確認の限界</summary><ol>'+''.join('<li>'+E(x)+'</li>' for x in next_actions)+'</ol><ul>'+''.join('<li>'+E(x)+'</li>' for x in d['limitations'])+'</ul></details>'
html=html.replace('<footer>',summary+'<footer>',1)
assert html.count('class="horse-finish"')==25 and html.count('class="score pending"')==25
assert '{E(' not in html
(OUT/(NAME+'.html')).write_text(html,encoding='utf-8')
md='# 2026-10-18 高知・佐賀の最終レース反省\n\n本線5点500円→150円、−350円。実購入未確認。\n\n'+'\n\n'.join('## '+r['venue']+'11R\n\n'+'\n\n'.join(r['notes']) for r in races)+'\n\n## 指数\n\n全25頭が90−2×順位。能力差の計算値ではなく順位表示用数値だった。未算出を明示し、元の固定JSONは保持する。\n\n## 次回\n\n'+'\n\n'.join(next_actions)
(OUT/(NAME+'.md')).write_text(md+'\n',encoding='utf-8')
verification=dict(reviewed_at=NOW,forecast_sha256=o['forecast_sha256'],forecast_unchanged=True,races=2,horses=25,settlements=totals,ordinal_formula_matches=25,html_horse_rows=25,html_uncomputed_scores=25,post_event_diagnostics_blind=False,actual_purchase=None)
(OUT/'verification.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for file in ['build_review.py','fetch_review_sources.py']:shutil.copy2(ROOT/file,OUT/file)
dest=SHARED/'outputs/nar20261018_review';dest.mkdir(parents=True,exist_ok=True)
shutil.copytree(OUT,dest,dirs_exist_ok=True)
print(json.dumps(verification,ensure_ascii=False))
