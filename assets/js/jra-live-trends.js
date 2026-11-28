(() => {
  'use strict';
  const config=JSON.parse(document.getElementById('day-forecast').textContent);
  if(!config.liveTrends)return;
  const feeds=JSON.parse(document.getElementById('day-results').textContent);
  const labels={turf:'芝',dirt:'ダート',hurdle:'障害'};
  const styleLabels=['逃げ','先行','差し','追込','未判定'];
  const kinds={wide:'ワイド',quinella:'馬連',trio:'三連複'};
  const esc=value=>String(value??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const table=(head,rows)=>'<table><thead><tr>'+head.map(v=>'<th>'+esc(v)+'</th>').join('')+'</tr></thead><tbody>'+rows.map(row=>'<tr>'+row.map(v=>'<td>'+esc(v)+'</td>').join('')+'</tr>').join('')+'</tbody></table>';
  const time=stamp=>stamp?stamp.slice(11,19)+' JST':'未確認';
  let activeRace=null,view='prediction',surface='turf';
  function current(){
    return config.races.find(r=>'#'+r.race_uid===location.hash)||config.races.find(r=>!document.getElementById(r.race_uid).hidden);
  }
  function stats(label,rows) {
    const placed=rows.filter(h=>Number.isInteger(h.finish)&&h.finish<=3);
    return [label,rows.filter(h=>h.finish===1).length,placed.length+' / '+rows.length,rows.length?(100*placed.length/rows.length).toFixed(0)+'%':'—',placed.filter(h=>h.pop>=4).length];
  }
  function trend(race,feed){
    const selected=(feed?.races||[]).filter(rr=>rr.status==='confirmed'&&config.races.some(r=>r.venue_key===race.venue_key&&r.race===rr.race&&r.surface===surface));
    const rows=[];
    for(const rr of selected){
      const original=config.races.find(r=>r.venue_key===race.venue_key&&r.race===rr.race);
      const started=rr.rows.filter(h=>!['withdrawn','excluded'].includes(h.runner_status)&&!['取消','除外'].includes(h.finish));
      for(const row of started){
        const horse=original.horses.find(h=>h.number===row.number);
        const first=row.corners?.[0];
        const position=Number.isInteger(first)?(first-1)/Math.max(1,started.length-1):null;
        const style=position===null?4:first===1?0:position<=.38?1:position<=.7?2:3;
        rows.push({...row,frame:row.frame??horse?.frame,style,pop:Number(row.final_popularity)||null,jockey:row.jockey||null});
      }
    }
    const buttons='<div class="live-surface">'+Object.entries(labels).filter(([k])=>k!=='hurdle'||race.surface==='hurdle').map(([k,v])=>'<button type="button" data-live-surface="'+k+'" aria-pressed="'+(surface===k)+'">'+v+'</button>').join('')+'</div>';
    const note='<p class="live-small">'+esc(race.venue)+' '+labels[surface]+'　確定 '+selected.length+'R・延べ'+rows.length+'頭 / 保存 '+time(feed?.updated_at)+'</p>';
    if(!selected.length)return buttons+note+'<p>まだ該当条件の確定結果はありません。</p>';
    const head=['区分','勝','3着内/出走','3着内率','4人気以下圏内'];
    const frames=Array.from({length:8},(_,i)=>stats((i+1)+'枠',rows.filter(h=>h.frame===i+1)));
    const frameMissing=rows.filter(h=>!h.frame);
    if(frameMissing.length)frames.push(stats('枠不明',frameMissing));
    const jockeys=[...new Set(rows.map(h=>h.jockey).filter(Boolean))].map(name=>stats(name,rows.filter(h=>h.jockey===name))).sort((a,b)=>b[1]-a[1]||a[0].localeCompare(b[0],'ja'));
    return buttons+note+'<h3>脚質別</h3>'+table(head,styleLabels.map((label,i)=>stats(label,rows.filter(h=>h.style===i))))+
      '<details><summary>脚質の分類</summary><p>実際の最初の通過順位。1番手を逃げ、残りは頭数に対する位置の比率で先行・差し・追込へ分ける推定です。通過順のない馬は未判定。</p></details>'+
      '<h3>枠の傾向</h3>'+table(head,[stats('内 1〜4',rows.filter(h=>h.frame>=1&&h.frame<=4)),stats('外 5〜8',rows.filter(h=>h.frame>=5&&h.frame<=8))])+
      '<details><summary>1〜8枠の内訳を見る</summary>'+table(head,frames)+'</details><h3>騎手別（'+labels[surface]+'）</h3>'+table(head,jockeys)+
      '<p class="live-small">距離・級の異なる当日レースを含みます。少数例・人気馬への騎乗・出走構成の違いがあるため、集計から自動で加点しません。</p>';
  }
  function market(race,feed,history=false){
    const record=feed?.market?.[String(race.race)];
    const snaps=record?.snapshots||[];
    const latest=snaps.at(-1);
    const closed=Date.parse(race.start_at)<=Date.now();
    const status=latest?(closed?'発走前の保存価格':Date.now()-Date.parse(latest.checked_at)>12*60000?'更新間隔超過・要確認':'最新取得'):'朝版のみ（発走90分前から取得予定）';
    const summary='<p class="live-small">'+esc(status)+' / '+time(latest?.checked_at||config.fixedAt)+(record?.error?' / 取得失敗・前回を保持':'')+'</p>';
    if(history){
      const rows=snaps.map(s=>[time(s.checked_at),s.tickets.map(t=>(kinds[t.kind]||t.kind)+' '+t.numbers.join('-')+' '+(t.lower??'未取得')).join(' / '),s.runners.filter(h=>h.status!=='出走').map(h=>h.number+' '+h.status).join('・')||'—']).reverse();
      return summary+'<h3>朝版の印を保存</h3><p>固定 '+time(config.fixedAt)+'。オッズ・取消・確定結果の更新を別記します。自動での印の変更は保留。</p>'+table(['取得','本線価格（下限）','取消等'],rows);
    }
    const rows=[...race.horses].sort((a,b)=>(a.rank??999)-(b.rank??999)).map(h=>{
      const fresh=latest?.runners.find(x=>x.number===h.number);
      return [h.number+' '+h.name,h.win,fresh?(fresh.status==='出走'?fresh.win:fresh.status):'—',fresh?.body||'—'];
    });
    const tickets=latest?.tickets||[];
    const retired=new Set((latest?.runners||[]).filter(h=>h.status!=='出走').map(h=>h.number));
    const eligible=tickets.length&&tickets.every(t=>t.lower!==null&&t.lower>=t.minimum&&!t.numbers.some(n=>retired.has(n)));
    const main='<h3>本線の価格条件</h3>'+(!tickets.length?'<p>最新の組合せ価格は未取得、または本線なし。</p>':table(['組合せ','最新価格','必要下限'],tickets.map(t=>[(kinds[t.kind]||t.kind)+' '+t.numbers.join('-'),t.lower===null?'未取得':t.lower===t.upper?t.lower:t.lower+'〜'+t.upper,t.minimum]))+'<p>'+esc(closed?'発走済み':eligible?'全点の表示価格条件を達成（直前確認が必要）':'価格未達・欠損・取消等により見送り')+'</p>');
    const cautions=(latest?.runners||[]).filter(h=>h.status!=='出走'||h.jockey&&race.horses.find(x=>x.number===h.number)?.jockey?.replace(/\s/g,'')!==h.jockey.replace(/\s/g,'')).map(h=>h.number+'番 '+h.status+'・'+h.jockey);
    return summary+main+(cautions.length?'<p>変更確認：'+esc(cautions.join(' / '))+'。印・買い目の再評価が必要です。</p>':'')+
      '<h3>全頭の単勝推移</h3>'+table(['馬番・馬名','朝','最新','馬体重'],rows);
  }
  function render(){
    const race=current();
    if(!race)return;
    const changed=activeRace!==race.race_uid;
    if(changed){activeRace=race.race_uid;surface=race.surface||'turf';}
    for(const r of config.races){
      const body=document.getElementById(r.race_uid)?.querySelector('.race-body');
      if(!body?.querySelector('.live-nav'))continue;
      const panel=body.querySelector('.live-panel');
      const visible=r.race_uid===activeRace&&view!=='prediction';
      body.classList.toggle('live-mode',visible);
      panel.hidden=!visible;
      for(const button of body.querySelectorAll('[data-live-view]'))button.setAttribute('aria-pressed',String(button.dataset.liveView===(r.race_uid===activeRace?view:'prediction')));
      if(visible)panel.innerHTML=view==='trends'?trend(r,feeds[r.venue_key]):market(r,feeds[r.venue_key],view==='history');
    }
  }
  document.addEventListener('click',e=>{
    const button=e.target.closest('[data-live-view],[data-live-surface]');
    if(button){
      if(button.dataset.liveView)view=button.dataset.liveView;
      if(button.dataset.liveSurface)surface=button.dataset.liveSurface;
      render();
    } else if(e.target.closest('#venue-tabs,.race-jumps,.featured-picks,.quick-picks'))setTimeout(render,0);
  });
  document.getElementById('horse-search').addEventListener('input',render);
  document.getElementById('race-filter').addEventListener('change',render);
  window.addEventListener('hashchange',render);
  window.addEventListener('kba:results',e=>{feeds[e.detail.key]=e.detail.data;render();});
  render();
})();
