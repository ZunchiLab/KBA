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
  const revisionFor=(race,feed)=>{
    const start=Date.parse(race.start_at);
    return (feed?.market?.[String(race.race)]?.snapshots||[]).filter(s=>s.revision&&Date.parse(s.revision.calculated_at)<start).at(-1)?.revision;
  };
  const horseName=(race,n)=>n+' '+(race.horses.find(h=>h.number===n)?.name||'');
  function revisionReason(entry){
    if(!entry)return '';
    return entry.factors.filter(f=>f.weight!==0).map(f=>{
      if(f.field==='market')return '単勝 '+f.morning_odds+'→'+f.latest_odds+'倍（相対支持 '+Math.round((f.ratio-1)*100)+'%）';
      const label=f.field==='jockey'?'騎手':f.field==='style'?'脚質':'枠';
      return label+' '+f.group+' '+f.placed+'/'+f.starts+'頭、人気帯比較 '+(f.difference>=0?'+':'')+Math.round(f.difference*100)+'pt';
    }).join('／')||'近接候補の比較または取消による順位変化';
  }
  function renderRevision(race,body,feed){
    const target=body.querySelector('.live-revision');
    if(!target)return;
    const revision=revisionFor(race,feed);
    if(!revision){
      target.hidden=false;
      target.innerHTML='<b>朝版の印</b><p class="live-small">直前予想の取得・再評価待ち</p>';
      return;
    }
    const ordered=revision.order;
    const changed=revision.changes||[];
    const withdrawn=new Set(revision.withdrawn||[]);
    const isMarket=revision.mode==='市場参考';
    const afterStart=Date.parse(race.start_at)<=Date.now();
    const stale=!afterStart&&Date.now()-Date.parse(revision.calculated_at)>12*60000;
    const existingFeed=feed?.market?.[String(race.race)];
    const errored=Boolean(existingFeed?.error);
    const hold=stale||errored;
    const main=revision.main_review;
    const label=isMarket?'市場参考順':revision.mode==='比較保留'?'参考順':'最新予想印';
    const marked=ordered.filter(n=>revision.marks[String(n)]!=='無印');
    const leaders=(marked.length?marked:ordered.slice(0,4)).map(n=>revision.marks[String(n)]!=='無印'?revision.marks[String(n)]+' '+horseName(race,n):horseName(race,n));
    const orderText=leaders.map(esc).join('　');
    const changeText=changed.length?changed.map(c=>c.number+'番 '+c.from_rank+'→'+c.to_rank+'位').join('・'):'朝から順位変更なし';
    const tickets=main.tickets||[];
    const mainText=afterStart?'発走前に保存した判断':hold?'更新未確認・見送り':main.decision==='条件達成'?'表示価格条件達成':'見送り';
    const card=body.closest('.race');
    if(!afterStart){
      const ready=!hold&&main.decision==='条件達成';
      card.dataset.bets=String(ready);
      const badge=card.querySelector('.decision-badge');
      if(badge){badge.textContent=ready?'直前価格条件達成':'直前見送り';badge.classList.toggle('buy',ready);badge.classList.toggle('skip',!ready);}
    }
    const ticketText=tickets.length?'<p><b>'+esc(kinds[main.kind]||main.kind)+' '+tickets.map(t=>esc(t.numbers.join('−')+' '+t.lower+(t.upper!==t.lower?'〜'+t.upper:'')+'倍（下限'+t.minimum+'）')).join(' / ')+'</b></p><p class="live-small">'+tickets.length+'点・'+tickets.reduce((n,t)=>n+(t.example_stake_yen||0),0).toLocaleString()+'円例</p>':'';
    const rows=changed.map(c=>[horseName(race,c.number),c.from_rank+'→'+c.to_rank,revisionReason(revision.horse_evidence.find(e=>e.number===c.number))]);
    const reasonDetails=rows.length?'<details><summary>変更理由 '+rows.length+'頭</summary>'+table(['馬','順位','根拠'],rows)+'</details>':'';
    const preservedOpen=target.querySelector('details')?.open;
    target.hidden=false;
    target.innerHTML='<div class="live-revision-title"><b>'+label+'</b><small>'+time(revision.calculated_at)+'</small></div><p class="live-current-order">'+orderText+'</p><p>'+esc(changeText+(withdrawn.size?'／取消・除外 '+[...withdrawn].join('・')+'番':''))+'</p>'+reasonDetails+
      '<p class="live-small">同馬場の確定 '+revision.same_surface_results.length+'R。'+(revision.trend_used?'人気帯と照合した脚質・枠・騎手の傾向も比較。':'件数不足のため馬場傾向の補正は保留。')+' 未校正の試験的判断。</p><h4>直前の買い目判定　'+esc(mainText)+'</h4>'+ticketText+
      '<p class="live-small">'+esc(main.reason)+' 全頭の状態・締切前の価格は別途確認。朝の買い目・近走指標は下に保存。</p>';
    if(preservedOpen&&target.querySelector('details'))target.querySelector('details').open=true;
    const rankSelect=body.querySelector('.horse-sort');
    for(const horse of body.querySelectorAll('.horse')){
      const n=Number(horse.dataset.number);
      const newRank=ordered.indexOf(n)+1;
      const mark=horse.querySelector('.mark');
      const sub=horse.querySelector('.horse-label small');
      if(!horse.dataset.morningMark)horse.dataset.morningMark=mark.textContent;
      if(sub&&!horse.dataset.morningLabel)horse.dataset.morningLabel=sub.textContent;
      if(newRank>0){
        horse.dataset.rank=String(newRank);horse.dataset.inactive='false';
        mark.textContent=revision.marks[String(n)]||'無印';
        if(sub)sub.textContent=(isMarket?'最新市場 ':'最新 ')+newRank+'番手 · 朝'+(race.horses.find(h=>h.number===n)?.rank??'—')+'番手'+(race.horses.find(h=>h.number===n)?.style?' · '+race.horses.find(h=>h.number===n).style:'');
      } else if(withdrawn.has(n)){
        horse.dataset.rank='';horse.dataset.inactive='true';mark.textContent='取消等';
        if(sub)sub.textContent='直前情報で取消・除外';
      }
      horse.classList.toggle('live-rank-changed',changed.some(c=>c.number===n));
      const chip=horse.querySelector('.ticket-horse');
      if(chip&&!chip.textContent.startsWith('朝'))chip.textContent='朝 '+chip.textContent;
    }
    if(rankSelect){
      rankSelect.querySelector('option[value=rank]').textContent=isMarket?'最新の市場参考順':'最新の予想印順';
      rankSelect.dispatchEvent(new Event('change'));
    }
    for(const section of body.querySelectorAll('.order-panel,.main-plan,.buy-guide')){
      if(!section.dataset.morningPlan){
        const badge=document.createElement('small');
        badge.className='live-morning-label';badge.textContent='朝版';
        section.prepend(badge);section.dataset.morningPlan='true';
      }
    }
    // The current order and decision are shown above; frozen plan controls remain archival.
    body.closest('.race').querySelectorAll('.copy-plan').forEach(btn=>{btn.disabled=true;btn.title='朝版の保存買い目です。直前判定を確認してください。';});
  }
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
      '<p class="live-small">距離・級の異なる当日レースを含みます。資料量と人気帯を確認した場合だけ試験的な順位補正を行います。</p>';
  }
  function market(race,feed,history=false){
    const record=feed?.market?.[String(race.race)];
    const snaps=record?.snapshots||[];
    const latest=snaps.at(-1);
    const closed=Date.parse(race.start_at)<=Date.now();
    const status=latest?(closed?'発走前の保存価格':Date.now()-Date.parse(latest.checked_at)>12*60000?'更新間隔超過・要確認':'最新取得'):'朝版のみ（発走90分前から取得予定）';
    const summary='<p class="live-small">'+esc(status)+' / '+time(latest?.checked_at||config.fixedAt)+(record?.error?' / 取得失敗・前回を保持':'')+'</p>';
    if(history){
      const rows=snaps.map(s=>[time(s.revision?.calculated_at||s.checked_at),s.revision?s.revision.order.slice(0,7).map(n=>(s.revision.marks[String(n)]||'')+n).join(' '):'再評価前',s.revision?.changes?.length?s.revision.changes.map(c=>c.number+':'+c.from_rank+'→'+c.to_rank).join(' '):'—',s.tickets.map(t=>t.numbers.join('-')+' '+(t.lower??'未取得')).join(' / ')]).reverse();
      return summary+'<h3>朝版と直前予想の履歴</h3><p>朝固定 '+time(config.fixedAt)+'。更新時刻ごとの印順と変更を保存。</p>'+table(['取得','上位印','順位変化','本線価格'],rows);
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
      renderRevision(r,body,feeds[r.venue_key]);
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
