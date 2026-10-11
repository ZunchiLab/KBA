from pathlib import Path
from datetime import datetime,timezone,timedelta
from collections import defaultdict
from html import escape
import json,hashlib,shutil
ROOT=Path(__file__).resolve().parent;PROJECT=ROOT.parents[1];REPO=PROJECT/'work/nar20261011/publish-repo';OUT=PROJECT/'outputs/nar20261011_review';SHARED=PROJECT.parent.parent/'2026-09-26/referenced-chatgpt-conversation-this-is-an/outputs/nar20261011_review'
NAME='report_20261011_nar_review_v1';NOW=datetime.now(timezone(timedelta(hours=9))).isoformat(timespec='seconds');E=lambda x:escape(str(x),quote=True)
f=json.loads((REPO/'predictions/report_20261011_nar_predictions_v1.json').read_text(encoding='utf-8-sig'));o=json.loads((OUT/'official_verification.json').read_text(encoding='utf-8'));rrs={r['race_uid']:r for r in o['results']}
NOTES={
('kochi',5):['◎9→○1→▲10。ワイド1−9は組合せ的中140円。','9・1の直近当地1300m勝ちを評価し、10の金沢交流2着も候補に残した。保存価格1.9〜2.4倍の下限1.9は最低2.5倍未達で見送り。','同距離の勝ちと転入実績を分ける比較を継続。結果から最低2.5倍を下げない。'],
('kochi',6):['勝ち馬2を8位。圏内候補8・7・10は5・7・6着。購入は事前見送り。','2の当地1400m2勝・2着1回・3着4回を保存していたが、直近1600m5着・1300m6着を重く見た。勝つ候補1は2着、5は5位で3着。','距離が戻る2と、現級好走8・昇級1・7を同じ1400mの材料で比較する。見送りと順位失敗は別に評価。'],
('kochi',7):['勝ち候補3が1着、共通軸11が2着。それでも掲載ワイド2点は不的中。','3の直近同走3着・1400m勝ちを事前に把握しながら、相手を6・9に限定。6は4着、9は5着。800m2着・中央経験の8も馬券外で3着。','発走前固定済みの順位基準は6−11・3−11の同じ2点200円で230円。実購入ではない。勝つ候補3を相手枠で6・9と直接比較することが事前に可能だった。'],
('kochi',8):['◎8→▲7→☆1。掲載馬連7−8は的中680円。','8の当地1300m実績、7の直近1300m2着を残した。連対軸4・8の一方8は連対、4は4着。全5点500円なら680円だが1−8が保存5.6倍で最低6倍未達、案全体は見送り。','候補捕捉・群制限・全点価格を分ける。結果後に7−8だけを購入した成績へ置換しない。'],
('kochi',9):['勝ち馬3を7位、勝つ候補4・5は6・8着。購入は見送り。','3の8/2 A−2勝ちを残しても、直近A−3と重賞の圏外を重く見た。2の当地1400m1勝2着1回も再比較が弱く5位から2着。9は距離実績を評価し3着候補に残せた。','3と5を直近同走とした記述は誤り。3の9/27はA−3・1600m、5は珊瑚冠賞・1900mで別レース。訂正注記を追加。同走・先着の文は両馬の同じrun_idを必須とする。'],
('kochi',10):['勝つ候補3が1着、◎1が2着、○2が3着。購入は見送り。','3の当地1400m9勝・2着6回・3着1回と春の1400m勝ちを保持し勝つ候補へ残したが、約5か月の休養状態未確認から総合6位。今回の勝ちだけで休養懸念が不要だったとは言えない。','能力材料と状態不明の評価幅を別表示。復帰状態を取りに行けない場合の購入見送りと、低能力への順位付けを分ける。'],
('kochi',11):['勝ち馬5を10位、暫定◎2は4着。購入は見送り。','1・8を圏内候補に残し2・3着を捕捉したが勝ち評価は失敗。5の直近1300m7着2.0秒差と1400m7着2.3秒差を優先。800m2着は評価幅に残せたが、それだけで今回1300m勝ちを必然とは説明できない。','記者選抜の相手変更と少数戦歴の未知を表示し、暫定順位を強い能力順として扱わない。最後のレースだからと買い足さない。'],
('saga',5):['◎6→▲5→○8。掲載ワイド6−8は的中250円。','6の初出走1300m勝ち、8の連続1300m2着を役割別に採用、5の1400m勝ちも上位に保持。保存下限2.3倍は最低2.5倍未達で見送り。','少数戦歴1勝を安定性の証明にしない。最終払戻250円で保存時の採否を逆転しない。'],
('saga',6):['◎11→○8→△4。購入は事前見送り。','11の直近1400m0.4秒差、8の同走比較、4の1300m実績を上位5頭に保持。上位3頭は11・8・9で3着4を揃えられない。','見送り中の好走も同じ分母で記録。転入の未知がどの相手枠を変えるかを具体的に比較する。結果後に11−8を購入したことにしない。'],
('saga',7):['◎・圏内軸3が1着。相手7は8着、2は4着でワイド2点不的中。','3の近3走3・2・2着は圏内根拠になったが、勝つ候補7・2に含めない判断も不足。2着1は8位・休養状態未知、3着8は4位・初1300m未知で馬券外。1は当地1300m3着、8は中央1000m3着と短縮材料が保存済み。','3の相手2枠で7・2と1・8を同じ基準で比較。事後の3−1は720円、3−8は370円だが、この組替えは事前成績へ加えない。'],
('saga',8):['○6→☆5→▲7。購入は事前見送り。3は競走除外。','直近同じ1400mで小差だった4・7・6・5を上位4頭に残したが暫定◎4は4着。比較不能として見送ったことが常に最適という証明ではない。','同走小差は勝敗固定より評価幅に使う。除外3を通常の圏外・実走へ数えない。'],
('saga',9):['◎10→○1→☆8。勝つ比較は捕捉したが価格達成の9−10は不的中。','10・1の直近同走小差を評価し1・2着を捕捉。8のA2勝ちも保持。9は4着。的中1−10は保存下限1.8倍が最低2倍未達、払戻130円。別案馬連1−10は160円、全5点500円なら赤字で保存価格でも全案見送り。','低配当点を外すだけでは9の同時好走が強くならない。相手1・8・9の能力比較と価格採否を混ぜない。'],
('saga',10):['転入8→共通軸10→5。相手2は4着、9は8着で掲載ワイド不的中。','10の当地1400m連勝は圏内根拠となった。8の高知B級2着を把握しながら当地未知で6位・馬券外。5の1300m0.8秒差・1400m0.6秒差と3着も5位・馬券外。保存価格達成の2−10が外れた。','8と5を採用相手2・9と同じ項目で比較。展開説明に8の先行を置くだけで、相手から除く理由は十分ではない。'],
('saga',11):['△8→◎14→○3。掲載三連複3−8−14は組合せ的中。','14の1400m2・3着、3の1300m連続3着、8の第3群を12点で包含し群制限では外れていない。本線3−14は260円だが保存1.9倍で最低3倍未達。採用13−14は不的中。三連複3−8−14の保存14.5倍は最低15倍未達、全案見送り。価格無視でも1,200円→1,330円の小幅利益。','8の1300m小差2走と900m2着を13・2の1400m小差と比較。三連複は本線との入替え。結果に合わせ15倍を下げたり全案を足したりしない。']}
NEXT=[
('P0','相手枠の直接比較','勝つ候補、保存人気上位4頭、条件戻り、休養・転入でも強い過去実績がある馬を群外へ置く場合、軸以外の採用相手と根拠走・距離・級・近況・位置取り・未知を比較する。説明できなければ固定軸案を見送る。','高知7R3、佐賀7R1・8、佐賀10R8・5'),
('P0','同走・先着の事実照合','両馬の根拠走IDが同じか確認。別レースの時計・着差を直接対戦と書かない。級文字列の一致だけで本文の正確さを保証しない。','高知9R3と5の誤記'),
('P1','能力と状態未知を別表示','休養・転入・初距離を低能力に置換しない。既知の能力と評価幅を残し、調教・当日状態を確認できない場合の購入見送りを別に決める。','高知10R3、佐賀7R1、佐賀10R8'),
('P1','価格条件を先に決め直前に確認','予算と的中の優先度を先に定め、全案費用と1点払戻を比較。少投票の早期価格だけで相手を決めない。締切前の価格・取消・馬場・状態を確認し発走前の新しい版へ保存できる場合だけ採否を再判定。未確認なら見送り。','価格達成本線700円→0円、全点1,700円→1,460円'),
('P1','全点価格条件の影響を明示','1点未達で案全体を見送る場合、候補捕捉と価格不採用を別表示。都合のよい点だけへ減らさない。点数・配分を変えるなら結果前に別案として固定。','高知8R馬連、佐賀11R三連複'),
('P2','全対象と同費用基準で検証','全14R、購入候補8R、保存価格候補5Rを別集計。軸外・相手外・群外・価格見送りを分離。同時点の順位・人気基準と同点数・同費用で比較し、未知の複数開催で確認。','本線1,700円→1,460円、順位1,690円、人気930円')]
KINDS={'wide':'ワイド','quinella':'馬連複','trio':'三連複'}
def eligible(p):
 ts=p['tickets']
 return ts if p['price_rule']=='all_tickets_required' and all(t['price_condition_at_snapshot'] is True for t in ts) else [] if p['price_rule']=='all_tickets_required' else [t for t in ts if t['price_condition_at_snapshot'] is True]
def settle(p,rr):
 prizes=[q for q in rr['refunds'] if q['kind']==KINDS[p['kind']]];assert prizes;fin={x['number']:x['finish'] for x in rr['rows']};accepted={tuple(t['numbers']) for t in eligible(p)};ts=[]
 for t in p['tickets']:
  assert all(isinstance(fin[x],int) for x in t['numbers']),'返還照合が必要'
  money=sum(q['yen_per_100'] for q in prizes if sorted(q['numbers'])==sorted(t['numbers']));ts.append(dict(t,hit=money>0,official_yen_per_100=money,payout_yen=money*t['example_stake_yen']//100,saved_price_eligible=tuple(t['numbers']) in accepted))
 def score(xs):return dict(points=len(xs),cost_yen=sum(t['example_stake_yen'] for t in xs),payout_yen=sum(t['payout_yen'] for t in xs),hit_points=sum(t['hit'] for t in xs),hit_races=int(any(t['hit'] for t in xs)),candidate_races=int(bool(xs)))
 return dict(plan_id=p['plan_id'],kind=p['kind'],role=p.get('role','diagnostic'),price_rule=p['price_rule'],groups=p.get('groups'),original_plan=p,tickets=ts,all_listed=score(ts),saved_price=score([t for t in ts if t['saved_price_eligible']]))
def add(a,b):
 for k,v in b.items():a[k]+=v
def finish(a):
 a=dict(a);a['net_yen']=a['payout_yen']-a['cost_yen'];a['return_percent']=round(a['payout_yen']/a['cost_yen']*100,1) if a['cost_yen'] else None;return a
M=defaultdict(lambda:defaultdict(int));totals=defaultdict(lambda:defaultdict(int));races=[]
for r in f['races']:
 rr=rrs[r['race_uid']];fin={x['number']:x['finish'] for x in rr['rows']};top=[x['number'] for x in rr['rows'] if isinstance(x['finish'],int) and x['finish']<=3];two=[x['number'] for x in rr['rows'] if isinstance(x['finish'],int) and x['finish']<=2];rank=[h['number'] for h in sorted(r['horses'],key=lambda h:h['rank'] or 999) if h['rank']];popular=sorted([h for h in r['horses'] if h['rank'] and h['market']['win'] is not None],key=lambda h:(h['market']['win'],h['number']));fav=popular[0]['number']
 for key in ['all',r['venue_key']]:
  m=M[key];m['races']+=1;m['listed_horses']+=len(r['horses']);m['starters']+=sum(isinstance(x,int) for x in fin.values());m['main_wins']+=fin[rank[0]]==1;m['main_top3']+=rank[0] in top;m['snapshot_favorite_wins']+=fin[fav]==1;m['snapshot_favorite_top3']+=fav in top;m['win_candidate_capture_races']+=any(fin[x]==1 for x in r['analysis']['win_candidates']);m['podium_slots']+=len(top);m['purchase_candidate_races']+=bool(r['bet_plans'])
  for k in [3,5,6,7]:m[f'top{k}_capture']+=len(set(top)&set(rank[:k]));m[f'top{k}_complete_races']+=set(top)<=set(rank[:k])
 plans=[settle(p,rr) for p in r['bet_plans']];baselines=[];diagnoses=[]
 for p in plans:
  if p['role']=='main':add(totals['main_all'],p['all_listed']);add(totals['main_price'],p['saved_price'])
  for b in r['analysis']['formation_review']['diagnostic_baselines']:
   if b['plan_id']!=p['plan_id']:continue
   q=settle(dict(b,role=p['role']),rr);q['method']=b['method'];baselines.append(q)
   if p['role']=='main':
    k='rank' if b['method']=='fixed_total_order' else 'popular';add(totals[k+'_all'],q['all_listed']);add(totals[k+'_price'],q['saved_price'])
  nums=set(x for t in p['tickets'] for x in t['numbers']);shared=set.intersection(*(set(t['numbers']) for t in p['tickets']));why='captured' if p['all_listed']['hit_races'] else 'axis_outside_top3' if shared and not shared<=set(top) else 'counterpart_outside_tickets'
  if p['kind']=='quinella':why='captured' if p['all_listed']['hit_races'] else 'axis_outside_top2' if not set(p['groups'][0])&set(two) else 'counterpart_outside_candidates' if not set(two)<=nums else 'group_excluded'
  if p['kind']=='trio':why='captured' if p['all_listed']['hit_races'] else 'axis_outside_top3' if not set(p['groups'][0])<=set(top) else 'counterpart_outside_candidates' if not set(top)<=nums else 'group_excluded'
  diagnoses.append(dict(plan_id=p['plan_id'],role=p['role'],classification=why,shared_numbers=sorted(shared),shared_axis_captured=shared<=set(top) if shared else None,winning_tickets_removed_by_price=[t['numbers'] for t in p['tickets'] if t['hit'] and not t['saved_price_eligible']]))
 horses=[dict(h,finish=fin[h['number']],official=next(x for x in rr['rows'] if x['number']==h['number'])) for h in r['horses']]
 races.append(dict(race_uid=r['race_uid'],venue=r['venue'],venue_key=r['venue_key'],race=r['race'],name=r['name'],top_three=top,rows=rr['rows'],refunds=rr['refunds'],source=rr['source'],original_analysis=r['analysis'],horses=horses,plans=plans,baselines=baselines,formation_diagnoses=diagnoses,notes=NOTES[r['venue_key'],r['race']],actual_purchase=None))
T={k:finish(v) for k,v in totals.items()};assert T['main_price']['cost_yen']==700 and T['main_price']['payout_yen']==0;assert T['main_all']['cost_yen']==1700 and T['main_all']['payout_yen']==1460
bad=next(r for r in f['races'] if r['venue_key']=='kochi' and r['race']==9);correction=dict(race_uid=bad['race_uid'],number=3,old_text='過去A－２勝ちは残すが直近同走では5の現級好走を優先。',text='高知9R③の「直近同走では⑤」は誤記。③の9/27はA−3・1600m、⑤は珊瑚冠賞・1900mで別レースです。直接対戦による先着比較ではありません。固定原本を保持し、この注記で訂正します。',evidence_refs=[next(h for h in bad['horses'] if h['number']==n)['past'][0]['run_id'] for n in [3,5]])
limitations=['当日通過順の列はあるが数値未掲載。映像未検証。先行競合・差し決着を敗因として断定しない。','上がり3F・一部時計は収集停止後に追加掲載。今回再取得した着順・払戻は公開結果と一致。','馬体重変化だけで体調や敗因を断定しない。調教・パドック未確認。','価格は17:22保存値。人気基準の同オッズは馬番順、未取得は末尾。最終人気とは別。','価格条件後の人気基準は1,300円、掲載・順位基準は700円。異なる費用を同予算の優劣としない。','全点診断は8R・17点1,700円の同費用比較。別案を後出しで合算しない。','実購入未確認。利用者の買い方や実損益を推定しない。金額は各100円の例。','今回の反省と次回手順は保存。係数修正・確率校正・未知開催の改善効果は未確認。']
d=dict(schema_version='kba.review/1',document_type='review',date_jst='2026-10-11',authority='nar',version='NAR-20261011-REVIEW-v1',venue='高知・佐賀',venues=f['venues'],phase='post_event_review',reviewed_at=NOW,forecast_sources=[dict(file='predictions/report_20261011_nar_predictions_v1.json',version='v1',fixed_at=f['fixed_at'],sha256=o['forecast_sha256'],hash_method='utf8-no-bom-lf-sha256')],actual_purchase=None,assumption='保存価格条件を適用し、直前の状態・取消・価格・締切も満たしたと仮定した掲載案の仮想検証。実購入未確認。',metrics={k:dict(v) for k,v in M.items()},settlements=T,races=races,results=[{k:v for k,v in r.items() if k not in ['raw_text','previous_source']} for r in o['results']],next_actions=[dict(priority=a,item=b,rule=c,evidence=e,status='次回の人手チェックへ保存。未知開催の効果未検証・地方の自動公開ゲート未実装。') for a,b,c,e in NEXT],errata=[correction],limitations=limitations)
(OUT/(NAME+'.json')).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Review data:',json.dumps(dict(metrics=d['metrics'],settlements=T),ensure_ascii=False))
