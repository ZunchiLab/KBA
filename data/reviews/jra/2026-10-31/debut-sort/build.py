from pathlib import Path
from datetime import datetime,timezone,timedelta
from hashlib import sha256
from html import escape
from collections import Counter
import json,sys,shutil
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[2];KBA=Path('C:/Users/furokei/Documents/Codex/KBA');OUT=ROOT/'outputs/20261031_debut_sort';STEM='jra-debut-sort-review-20261031-v1';PREVIEW='jra-role-index-preview-20261031-v3'
sys.path.insert(0,str(KBA/'scripts'));from render_jra_prediction import render
load=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
E=lambda x:escape(str(x),quote=True)
B=load(OUT/'並び順の全比較.json');D=load(OUT/'新馬追加見本データ.json');old=load(ROOT/'outputs/20261031/report_20261031_jra_predictions_v1.json');NOW=datetime.now(timezone(timedelta(hours=9))).isoformat(timespec='seconds')
raw=OUT/'調教掲載_261029.raw.html';soup=BeautifulSoup(raw.read_bytes(),'html.parser');training=[]
for r in old['races']:
 if r['class_text']!='新馬':continue
 for h in r['horses']:
  tr=next((tr for tr in soup.select('tr') if any(td.get_text(' ',strip=True)==h['name'] for td in tr.find_all('td'))),None)
  if tr:
   cells=[td.get_text(' ',strip=True) for td in tr.find_all('td')]
   training.append(dict(key=r['key'],number=h['number'],name=h['name'],listing_cells=cells,clock_scored=False,reason='掲載名の一致のみ確認。動画の時計・負荷・手応えの全頭比較は未完了。掲載の有無で加点しない。'))
source=dict(provider='JRAレーシングビュアー',url='https://prc.jp/jraracingviewer/contents/training/261029.html',retrieved_at=datetime.fromtimestamp(raw.stat().st_mtime,timezone(timedelta(hours=9))).isoformat(timespec="seconds"),raw_sha256=sha256(raw.read_bytes()).hexdigest(),raw_file=raw.name,not_available_at_original_snapshot=True)
save(OUT/'新馬の調教資料確認.json',dict(source=source,matched_listings=training,total_debut_horses=54,clock_scored=False,not_used_in_historical_indices=True))
stats=[h['role_indices'] for r in D['races'] if r['class_text']=='新馬' for h in r['horses']]
B.update(debut_implementation=dict(version='jra-debut-cohort-v1',horses=54,with_related_evidence=sum(bool(d['components']) for d in stats),minimum=min(d[k]['value'] for d in stats for k in ['first','second','top2','top3']),maximum=max(d[k]['value'] for d in stats for k in ['first','second','top2','top3']),source_corpus_observations=len(load(OUT/'新馬関連実績コーパス.json')['observations']),training_listing_matches=len(training),training_source=source,training_clock_scored=False),preview=PREVIEW+'.html',forecast_originals_changed=False)
B['limitations'].append('前回の集計は同点を馬番で処理。今回は実際の画面操作に合わせて朝の総合順位→馬番に統一したため、同点境界の捕捉数が前回表と少し異なる。')
save(OUT/(STEM+'.json'),B)
D.update(document_type='presentation',phase='post_event_presentation',generated_at=NOW,presentation_version='role-demo-v3',role_index_model=dict(version='jra-role-relative-v2+debut-cohort-v1',computed_after_results=True,calibrated=False,trained=False,input_cutoff_at=old['fixed_at'],reason='本人の実走とは別に、新馬の父・厩舎・騎手の過去関連実績を参考表示。全て開催後の設計・表示見本。'))
D['presentation']['day_notice']='開催後の見本・検証中。新馬54頭にも関連実績の4指標を追加しました。朝の印・順位・買い目は原本のまま。新方式の成績は新たな事前的中として扱いません。'
D['presentation']['storage_namespace']='role-indices-post-event-demo-v3'
D['source_forecast_model_version']=D['model_version'];D['model_version']='jra-role-relative-v2+debut-cohort-v1-post-event-demo'
if 'formula' in D['model']:D['model']['legacy_formula']=D['model'].pop('formula')
D['model']['definition']='既走はv2の同R相対実績。新馬は対象日より前の保存新馬戦における父・厩舎・騎手の関連実績。どちらも補助指標、未校正。'
for item in D.get('supplemental_files',[]):item['file']='../predictions/'+item['file']
save(OUT/(PREVIEW+'.json'),D)
official=load(ROOT/'outputs/20261031_review/公式結果_最終照合.json')
html=render(D,PREVIEW+'.json',official['venues']).replace('</header>','</header><p class="day-summary"><a href="'+STEM+'.html">新馬の対応・並び順の全比較 →</a></p>',1).replace('<details class="official-payouts" open>','<details class="official-payouts">').replace('<h1>10/31 JRA 本気予想</h1>','<h1>新馬にも4指標・検証中</h1>').replace('<title>2026-10-31 JRA 本気予想</title>','<title>新馬の4指標・並び替え見本（開催後）</title>')
(OUT/(PREVIEW+'.html')).write_text(html,encoding='utf-8')
css='*{box-sizing:border-box}body{margin:0;background:#f2f5f1;color:#193b30;font:15px/1.65 system-ui,"Yu Gothic",sans-serif}main{max-width:1000px;margin:auto;padding:18px 12px}h1{font-size:24px;line-height:1.4}h2{font-size:19px}h3{font-size:16px}p{margin:8px 0}section,details.card{background:white;border:1px solid #d9e3d8;border-radius:12px;padding:14px;margin:12px 0}a{color:#17654c}.links{display:flex;gap:8px;flex-wrap:wrap}.links a{padding:8px 12px;background:#173d32;color:white;border-radius:8px;text-decoration:none}.small{font-size:12px;color:#596f62;overflow-wrap:anywhere}.warn{border-left:4px solid #c49337;padding-left:10px}.scroll{overflow:auto}table{width:100%;border-collapse:collapse;font-size:13px}td,th{padding:8px 6px;text-align:left;border-bottom:1px solid #e0e6dd;white-space:nowrap}.best{background:#e6f1df;font-weight:bold}select,button{font:inherit;max-width:100%;padding:8px;border-radius:7px;border:1px solid #a5b9ab;background:white;color:#193b30}summary{cursor:pointer;font-weight:600}label{display:inline-block;margin:4px 8px 4px 0}#races .card{padding:11px}#races table{font-size:12px}.badge{background:#e4eddf;border-radius:5px;padding:4px 7px;font-size:12px}@media(max-width:420px){main{padding:12px 8px}section{padding:11px}h1{font-size:22px}}'
today=B['scopes']['today_all'];eight=B['scopes']['eight_days_flat']
def table(scope):
 return '<div class="scroll"><table><thead><tr><th>並び順</th><th>上位3頭</th><th>上位5頭</th><th>上位7頭</th><th>平均必要頭数</th></tr></thead><tbody>'+''.join('<tr><td>'+E(v['label'])+'</td>'+''.join('<td>'+str(v['all_inside'][str(k)])+'/'+str(v['races'])+'</td>' for k in [3,5,7])+'<td>'+str(v['mean_prefix'])+'</td></tr>' for m,v in scope.items() if m!='number')+'</tbody></table></div>'
embedded=json.dumps(dict(scopes=B['scopes'],rows=B['rows'],methods=B['methods']),ensure_ascii=False).replace('</','<\\/')
page=f'''<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>新馬の指標と並び順の検証</title><style>{css}</style></head><body><main><header><span class="badge">10/31全24R · 8開催日の比較</span><h1>3頭が上位に集まったのは<br>どの並び順だったか</h1><p>新馬54頭にも、朝の人気を使わない4指標の数値参考を追加しました。並び順ごとに「馬券内全頭が何位までにそろったか」を照合しました。</p><div class="links"><a href="{PREVIEW}.html?venue=tokyo#jra-2026-10-31-tokyo-r4">新馬の4指標を見る</a><a href="#compare">並び順を比較</a><a href="#races">レース別</a></div></header><section><h2>結論</h2><p>10/31全24Rの上位7頭への全包含は、朝人気14R・総合印順13R・3着内指標12R。8開催日193平地Rでも、上位5頭への全包含は朝人気69R・総合印順65R・3着内指標57Rです。</p><p class="warn">独自指標が人気基準より全般的に良いとは言えません。3着内指標は上位3頭だけでの全包含16/193Rと最多でしたが、上位5・7頭の比較では人気順が上です。都合のよい範囲だけを選びません。</p></section><section><h2>新馬も、できる材料から評価</h2><p>54頭すべてに関連実績があり、4指標は45.1〜57.9。前日までに取得済みの同馬場の新馬成績から、父・厩舎・騎手の一致例を集計します。同じ出走例の重複加点はしません。未知・少数例は極端な数値を抑えます。</p><p>ただし関連実績を使える同じ34新馬戦では、3着内参考の上位7頭での全包含は9R、朝人気は20R。最初の5Rは過去の保存実績がなく別扱いです。<b>新馬用の数値ができたことと、予測が強くなったことは別です。</b>単独での軸決めには使わず、調教・母系・条件との個別比較を補います。</p><details><summary>使った材料・調教の確認範囲</summary><p>保存8日・39新馬戦529出走例が全コーパス。各対象日では必ず前日以前かつ入力確認時点以前の資料だけに限定。通年の種牡馬・厩舎成績ではありません。</p><p>今週の公式映像サービス一覧では新馬54頭中{len(training)}頭の掲載名が一致。動画の時計・追った強さ・併せ馬・手応えの全頭比較は未完了です。映像がない馬を減点せず、掲載がある馬にも加点していません。母・きょうだいの網羅評価も未完了。</p><p><a href="{source['url']}">JRAレーシングビュアー・調教一覧</a> / 確認 {E(NOW)}。この開催後取得資料は過去指標へ使っていません。</p><p>新馬の値は本人の実績値ではなく「関連実績参考」。父40%・厩舎35%・騎手25%の一致重み、距離差・日数、少数例の平滑化を使用。係数は仮説で今回結果への最適化はしません。空の材料を平均能力と断定せず、全材料なしの場合は差を作らない50を表示します。</p></details></section><section id="compare"><h2>並び順の全比較</h2><p class="small">数値は馬券内の全頭が候補に含まれたレース数。馬券の的中数ではありません。全包含を調べる頭数と、実際に購入する点数は別です。</p><label>対象 <select id="scope"><option value="today_all">10/31全24R</option><option value="today_flat">10/31既走平地19R</option><option value="eight_days_flat">8開催日・既走平地193R</option><option value="today_debut">10/31新馬4R</option><option value="eight_days_debut_common">関連実績あり・新馬34R</option><option value="eight_days_debut">全新馬39R（資料なし含む）</option></select></label><div id="summary-table">{table(today)}</div><p id="available-note" class="small"></p><details><summary>8開催日193平地Rの表を開く</summary>{table(eight)}</details></section><section><h2>次の予想に反映すること</h2><ul><li>新馬も父・厩舎・騎手の関連実績を計算し、材料の薄さ・未確認の調教を明示。</li><li>朝人気順を並び替えへ追加。独自上位と市場上位の違いを、その場で比較できるように。</li><li>指標だけで候補を切らず、市場上位・条件戻り・古い好走・別展開を含めた直接比較で採否を決める。</li><li>次の未知開催も固定時点の人気基準を残し、同じ候補頭数で3頭捕捉を検証。表示変更や資料追加だけで精度改善を宣言しない。</li></ul><p class="small">上位5頭BOXの三連複は10点、上位7頭なら35点。広げれば費用も増えます。この表を全頭BOX購入の推奨にはしません。</p></section><section><h2>レース別の必要頭数</h2><p class="small">各並び順で、実際の馬券内全頭が初めてそろう位置を表示。最少の並び順は結果を知った後の診断で、発走前に選べた方式とは限りません。</p><label>開催日 <select id="day"></select></label><label>区分 <select id="category"><option value="all">全レース</option><option value="flat">既走平地</option><option value="debut">新馬</option></select></label><div id="races"></div></section><details class="card"><summary>出典・計算・限界・保存データ</summary><ul>{''.join('<li>'+E(x)+'</li>' for x in B['limitations'])}</ul><p>朝の総合印順は元のrank順。4役割は保存資料へv2を事後適用、新馬は関連実績参考。入力と計算時刻は別保存し、計算を朝へ遡らせません。全て結果既知の事後診断です。</p><p><a href="{STEM}.json">全レースの順位と比較JSON</a> / <a href="{STEM}.md">文章版</a> / <a href="../docs/jra-debut-indices.md">新馬の計算定義</a></p><p class="small">作成 {E(NOW)}。8開催日の元予想・結果のSHAを保存。発走前の印・順位・買い目・原本は変更していません。</p></details><p><a href="../index.html">一覧</a></p></main><script id="review-data" type="application/json">{embedded}</script><script>
const D=JSON.parse(document.getElementById('review-data').textContent),q=s=>document.querySelector(s),esc=x=>String(x).replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
function summary(){{const s=D.scopes[q('#scope').value];q('#summary-table').innerHTML='<div class="scroll"><table><thead><tr><th>並び順</th><th>上位3頭</th><th>上位5頭</th><th>上位7頭</th><th>平均必要頭数</th></tr></thead><tbody>'+Object.entries(s).filter(([k])=>k!=='number').map(([k,v])=>'<tr><td>'+esc(v.label)+'</td>'+[3,5,7].map(n=>'<td>'+v.all_inside[n]+'/'+v.races+'</td>').join('')+'<td>'+v.mean_prefix+'</td></tr>').join('')+'</tbody></table></div>';q('#available-note').textContent='新馬は関連実績がない日も残します。4参考の利用可能R：'+s.top3.available+'/'+s.top3.races+'。利用不可の成功数は加えません。平均は利用可能Rのみ。';}}
const days=[...new Set(D.rows.map(r=>r.date))].sort().reverse();q('#day').innerHTML=days.map(d=>'<option>'+d+'</option>').join('');
function races(){{const category=q('#category').value;const rows=D.rows.filter(r=>r.date===q('#day').value&&(category==='all'||(category==='debut'?r.class_text==='新馬':r.class_text!=='新馬'&&!['hurdle','障'].includes(r.surface))));q('#races').innerHTML=rows.map(r=>'<details class="card"><summary>'+esc(r.venue)+r.race_no+'R '+esc(r.class_text)+' · 3頭がそろう最少 '+r.hindsight_best_prefix+'頭</summary><p>実際：'+r.actual_placed.map(h=>h.finish+'着 '+h.number+' '+esc(h.name)).join(' / ')+'</p><div class="scroll"><table><thead><tr><th>並び順</th><th>必要頭数</th><th>馬券内各馬の表示順位</th></tr></thead><tbody>'+Object.entries(r.methods).filter(([k])=>k!=='number').map(([k,m])=>'<tr class="'+(m.available&&m.needed_prefix===r.hindsight_best_prefix?'best':'')+'"><td>'+esc(D.methods[k])+'</td><td>'+(m.available?m.needed_prefix+'頭':'材料なし')+'</td><td>'+m.placed_positions.map(p=>p.number+'番＝'+p.position+'位').join(' / ')+'</td></tr>').join('')+'</tbody></table></div><p class="small">緑は結果を知った後の最少。並び順を結果に合わせて事前選択した成績にはしません。</p></details>').join('');}}
q('#scope').addEventListener('change',summary);q('#day').addEventListener('change',races);q('#category').addEventListener('change',races);summary();races();
</script></body></html>'''
(OUT/(STEM+'.html')).write_text(page,encoding='utf-8')
md=['# 新馬指標・並び順検証','','開催後の設計・診断。元の予想は変更しない。','新馬54頭に4指標45.1〜57.9。父・厩舎・騎手の関連実績、調教は未採点。','同じ34新馬戦の上位7頭全包含：新馬3着内参考9R、朝人気20R。残る5Rは関連資料なし。優位性なし。','','| 並び順 | 10/31 上位3頭 | 上位5頭 | 上位7頭 | 8日193R 上位5頭 | 上位7頭 |','|---|---:|---:|---:|---:|---:|']
for m in ['rank','score','first','second','top2','top3','market']:
 a=today[m];b=eight[m];md.append('| '+a['label']+' | '+' | '.join(str(a['all_inside'][str(k)])+'/24' for k in [3,5,7])+' | '+str(b['all_inside']['5'])+'/193 | '+str(b['all_inside']['7'])+'/193 |')
md+=['','上位3着内指標の全包含は16/193Rと最多だが、上位5/7頭では市場基準が上。範囲を選んだ優位性の断定をしない。','全包含は馬券の的中ではない。同じ候補頭数で比較し、購入点数・費用は別に確認。']+B['limitations']
(OUT/(STEM+'.md')).write_text('\n'.join(md)+'\n',encoding='utf-8')
# Verify every original, original horse fields and ticket plans.
for a,b in zip(old['races'],D['races']):
 assert a['bet_plans']==b['bet_plans']
 for h,n in zip(a['horses'],b['horses']):assert h=={k:v for k,v in n.items() if k!='role_indices'}
rec=load(ROOT/'outputs/20261031/固定記録_v1.json')
for name,digest in rec['files'].items():assert sha256((ROOT/'outputs/20261031'/name).read_bytes()).hexdigest()==digest
for x in B['inputs']:assert sha256((KBA/x['path']).read_bytes()).hexdigest()==x['sha256']
ps=BeautifulSoup(html,'html.parser');assert len(ps.select('details.horse'))==305 and len(ps.select('select.horse-sort'))==24
assert all(len(s.find_all('option'))==8 for s in ps.select('select.horse-sort'))
record=dict(passed=True,checked_at=NOW,tests=dict(python=86,sort_js=8,compact_js=9,result_ui_js=24),debut_horses=54,related_examples_for_all=True,training_listings=len(training),training_clocks_scored=False,originals_unchanged=True,display_races=24,display_horses=305,sort_options=8,benchmark_races=len(B['rows']),same_ui_tie_break=True)
save(OUT/'検算.json',record);print(json.dumps(record,ensure_ascii=False))
