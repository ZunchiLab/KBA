(() => {
  'use strict';
  const config = JSON.parse(document.getElementById('day-forecast').textContent);
  const stored = JSON.parse(document.getElementById('day-results').textContent);
  const tabs = [...document.querySelectorAll('[role=tab]')];
  const panels = [...document.querySelectorAll('.venue-panel')];
  const cards = [...document.querySelectorAll('.race')];
  const status = document.getElementById('result-status');
  const button = document.getElementById('refresh-results');
  const labels = {confirmed:'全着順・払戻掲載',partial:'速報・全着順待ち',not_started:'保存時は発走前',pending:'確定待ち',error:'取得保留',cancelled:'競走取り止め'};
  let active = config.venues[0].venue_key;
  const viewStates = {};
  let forecastPromise;
  const storageKey = 'kba-day-plan:' + config.date + ':' + config.version;
  const escapeWhitespace = text => String(text).replace(/\s/g, '');
  function chooseVenue(key, updateURL=true) {
    if (!config.venues.some(v => v.venue_key===key)) key=config.venues[0].venue_key;
    const previous=active;
    if(updateURL) viewStates[previous]={search:document.getElementById('horse-search').value,filter:document.getElementById('race-filter').value,scroll:window.scrollY};
    active=key;
    if(previous!==key){document.getElementById('horse-search').value=viewStates[key]?.search||'';document.getElementById('race-filter').value=viewStates[key]?.filter||'all';}
    tabs.forEach(t => { const on=t.dataset.venue===key;t.setAttribute('aria-selected',String(on));t.tabIndex=on?0:-1; });
    panels.forEach(p => p.hidden=p.id!=='venue-'+key);
    document.querySelectorAll('.sticky .race-jumps').forEach(jumps=>jumps.hidden=jumps.dataset.venue!==key);
    if(updateURL) { const u=new URL(location.href);u.searchParams.set('venue',key);if(hashVenue()&&hashVenue()!==key)u.hash='';history.replaceState(null,'',u); }
    filter();
    if(updateURL&&previous!==key&&viewStates[key]) window.scrollTo({top:viewStates[key].scroll,behavior:'instant'});
  }
  function hashVenue() { return config.races.find(r => '#'+r.race_uid===location.hash)?.venue_key; }
  tabs.forEach((tab,i) => {
    tab.addEventListener('click',()=>chooseVenue(tab.dataset.venue));
    tab.addEventListener('keydown',event=>{
      const j=event.key==='Home'?0:event.key==='End'?tabs.length-1:event.key==='ArrowRight'?(i+1)%tabs.length:event.key==='ArrowLeft'?(i-1+tabs.length)%tabs.length:null;
      if(j!==null){event.preventDefault();chooseVenue(tabs[j].dataset.venue);tabs[j].focus();}
    });
  });
  function filter() {
    const q=document.getElementById('horse-search').value.trim().toLowerCase();
    const mode=document.getElementById('race-filter').value;
    const now=Date.now();let visible=0;
    cards.forEach(card=>{
      const closed=Date.parse(card.dataset.start)<=now;
      card.querySelector('.clock-state').textContent=closed?'発走時刻を経過':'';
      card.hidden=Boolean(q&&!card.dataset.search.toLowerCase().includes(q))||(mode==='buy'&&card.dataset.bets!=='true')||(mode==='future'&&closed);
      if(card.dataset.venue===active&&!card.hidden)visible++;
    });
    document.getElementById('empty-state').hidden=visible>0;
  }
  document.getElementById('horse-search').addEventListener('input',filter);
  document.getElementById('race-filter').addEventListener('change',filter);
  window.addEventListener('hashchange',()=>{if(hashVenue())chooseVenue(hashVenue());});
  chooseVenue(hashVenue()||new URL(location.href).searchParams.get('venue'),false);
  setInterval(filter,30000);
  try {
    const chosen=JSON.parse(localStorage.getItem(storageKey)||'{}');
    document.querySelectorAll('.plan-choice input').forEach(radio=>{if(chosen[radio.name]===radio.value)radio.checked=true;});
  } catch (_) { /* Storage can be disabled; the static plan still works. */ }
  function updateBudget() {
    let total=0;const choices={};
    document.querySelectorAll('.plan-choice input:checked').forEach(r=>{total+=Number(r.dataset.cost);choices[r.name]=r.value;});
    const el=document.getElementById('plan-total');
    el.textContent=`仮プラン全点合計 ${total.toLocaleString()}円 / 上限例 ${config.budget.day_limit_yen.toLocaleString()}円（購入未記録）`;
    el.classList.toggle('over-budget',total>config.budget.day_limit_yen);
    try {localStorage.setItem(storageKey,JSON.stringify(choices));} catch (_) {}
  }
  document.querySelectorAll('.plan-choice input').forEach(r=>r.addEventListener('change',updateBudget));updateBudget();
  document.querySelectorAll('.sort-horses').forEach(btn=>btn.addEventListener('click',()=>{
    const card=btn.closest('.race');const race=config.races.find(r=>r.race_uid===card.id);
    const byNumber=btn.dataset.order!=='number';const list=card.querySelector('.all-horses');
    const rank=n=>race.horses.find(h=>h.number===n).rank||999;
    [...list.children].sort((a,b)=>byNumber?Number(a.dataset.number)-Number(b.dataset.number):rank(Number(a.dataset.number))-rank(Number(b.dataset.number))).forEach(h=>list.append(h));
    btn.dataset.order=byNumber?'number':'rank';btn.textContent=byNumber?'総合順位順に切替':'馬番順に切替';
  }));
  function toast(message) { const e=document.createElement('div');e.className='toast';e.role='status';e.textContent=message;document.body.append(e);setTimeout(()=>e.remove(),4000); }
  document.querySelectorAll('.copy-plan').forEach(btn=>btn.addEventListener('click',async()=>{
    const race=config.races.find(r=>r.bet_plans.some(p=>p.plan_id===btn.dataset.planId));
    if(Date.parse(race.start_at)<=Date.now()){toast('発走時刻を過ぎたため、新規購入用コピーを停止しています。');return;}
    const p=race.bet_plans.find(p=>p.plan_id===btn.dataset.planId);
    const text=`${config.date} ${race.venue}${race.race}R ${p.type} ${p.role==='main'?'本線':'別案（本線と入替え）'}\n`+p.tickets.map(t=>`${t.numbers.join(p.ordered?'→':'−')} 各${t.example_stake_yen}円 最低${t.minimum_odds}倍 / 保存時${t.decision_at_snapshot}`).join('\n')+`\n全${p.points}点 最大${p.maximum_example_yen}円。直前価格・取消・状態が未確認なら見送り。実購入未記録。`;
    try {await navigator.clipboard.writeText(text);toast('買い目と価格条件をコピーしました。');} catch (_) {toast('コピーできませんでした。買い目表を参照してください。');}
  }));
  async function getJSON(url) {
    const c=new AbortController();const timer=setTimeout(()=>c.abort(),15000);
    try{const response=await fetch(url,{cache:'no-store',signal:c.signal});if(!response.ok)throw new Error('HTTP '+response.status);return await response.json();}finally{clearTimeout(timer);}
  }
  async function forecastHash() {
    if(!forecastPromise) forecastPromise=(async()=>{
      const c=new AbortController();const timer=setTimeout(()=>c.abort(),15000);
      try {
        const response=await fetch(config.jsonFile,{cache:'no-store',signal:c.signal});if(!response.ok)throw new Error('固定予想の取得失敗');
        const text=(await response.text()).replace(/^\uFEFF/,'').replace(/\r\n/g,'\n');const d=JSON.parse(text);
        if(d.date_jst!==config.date||d.forecast_version!==config.version)throw new Error('固定予想の版不一致');
        const hash=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(text));
        return [...new Uint8Array(hash)].map(b=>b.toString(16).padStart(2,'0')).join('');
      } finally {clearTimeout(timer);}
    })().catch(e=>{forecastPromise=null;throw e;});
    return forecastPromise;
  }
  function validate(data,key,digest) {
    const venue=config.venues.find(v=>v.venue_key===key);
    if(data.date_jst!==config.date||data.venue_key!==key||data.baba_code!==venue.baba_code||data.forecast_version!==config.version||(digest&&data.forecast_sha256!==digest))throw new Error('結果の対象・予想版が不一致');
    const expected=config.races.filter(r=>r.venue_key===key);const nums=new Set();
    for(const rr of data.races){
      const race=expected.find(r=>r.race===rr.race);if(!race||nums.has(rr.race))throw new Error('レース番号不一致');nums.add(rr.race);
      const runners=new Set();
      for(const row of rr.rows){const horse=race.horses.find(h=>h.number===row.number);if(!horse||runners.has(row.number)||escapeWhitespace(row.name)!==escapeWhitespace(horse.name))throw new Error('馬番・馬名不一致');runners.add(row.number);}
    }
    if(nums.size!==expected.length)throw new Error('対象レースの不足');
  }
  function merge(data,key) {
    const prev=stored[key];
    if(prev) for(let i=0;i<data.races.length;i++) {
      const r=data.races[i];const old=prev.races.find(p=>p.race===r.race);
      if(old&&(['confirmed','cancelled'].includes(old.status)&&!['confirmed','cancelled'].includes(r.status)||old.rows.length>0&&r.rows.length===0||Date.parse(prev.updated_at)>Date.parse(data.updated_at))) data.races[i]={...old,refresh_error:'新しい取得では確定情報が揃わず、既知の結果を保持'};
    }
    stored[key]=data;draw(key);
  }
  function draw(key) {
    const data=stored[key];if(!data)return;
    for(const rr of data.races){
      const race=config.races.find(r=>r.venue_key===key&&r.race===rr.race);const card=document.getElementById(race.race_uid);
      const note=card.querySelector('.race-result-status');note.replaceChildren();
      note.append((labels[rr.status]||'未確定')+' · 保存 '+data.updated_at.slice(5,16).replace('T',' ')+' JST');
      if(rr.source){const a=document.createElement('a');a.href=rr.source.url;a.textContent=' / 公式確認 '+rr.source.retrieved_at.slice(11,19)+' JST';note.append(a);}
      else if(rr.status==='error')note.append(' / 公式取得に失敗。着順をまだ保存できていません。');
      if(rr.refresh_error)note.append(' / 既知の結果を保持');
      for(const h of race.horses){const row=rr.rows.find(r=>r.number===h.number);const el=card.querySelector(`.horse[data-number="${h.number}"] .horse-finish`);
        el.textContent=row?(Number.isInteger(row.finish)?row.finish+'着':String(row.finish)):h.status_at_snapshot==='withdrawn'?'取消':rr.status==='cancelled'?'競走取止':rr.status==='not_started'?'保存時は発走前':'未確定';
        el.classList.toggle('podium',Boolean(row&&Number.isInteger(row.finish)&&row.finish<=3));
      }
      const payouts=card.querySelector('.payouts');payouts.replaceChildren();
      if(rr.refunds?.length){const det=document.createElement('details');const sum=document.createElement('summary');sum.textContent='公式払戻を見る（100円あたり）';det.append(sum);const ul=document.createElement('ul');for(const p of rr.refunds){const li=document.createElement('li');li.textContent=`${p.kind} ${p.combination} ${p.yen_per_100.toLocaleString()}円`;ul.append(li);}det.append(ul);payouts.append(det);}
      for(const plan of race.bet_plans){const el=card.querySelector(`[data-plan-result="${plan.plan_id}"]`);
        if(rr.status!=='confirmed'){el.textContent='掲載案の結果：確定待ち／実購入未記録';continue;}
        if(rr.rows.some(row=>!Number.isInteger(row.finish))){el.textContent='取消・除外等を含むため返還の照合待ち。収支判定は保留／実購入未記録';continue;}
        const eligible=plan.tickets.filter(t=>t.price_condition_at_snapshot===true);
        if(!eligible.length){el.textContent='保存価格条件では全点見送り／実購入未記録';continue;}
        const prices=rr.refunds.filter(p=>p.kind===plan.type);
        if(!prices.length){el.textContent='該当券種の払戻未確認。判定保留';continue;}
        let paid=0,cost=0,hits=0;
        for(const ticket of eligible){cost+=ticket.example_stake_yen;const same=x=>(plan.ordered?[...x]:[...x].sort((a,b)=>a-b)).join('-');const p=prices.find(p=>same(p.numbers)===same(ticket.numbers));if(p){hits++;paid+=p.yen_per_100*ticket.example_stake_yen/100;}}
        el.textContent=`保存価格条件だけでの参考照合：${hits}/${eligible.length}点的中、${cost}円→${paid}円。直前条件未確認・実購入収支ではありません。`;
      }
    }
  }
  for(const key of Object.keys(stored)){try{validate(stored[key],key,null);draw(key);}catch(_){delete stored[key];}}
  async function refresh(automatic=false) {
    if(button.disabled||automatic&&document.hidden||automatic&&config.venues.every(v=>stored[v.venue_key]?.complete))return;
    button.disabled=true;status.textContent='最新コミットと会場別結果を確認中…';
    try {
      const digest=await forecastHash();let base,origin;
      try {const head=await getJSON('https://api.github.com/repos/ZunchiLab/KBA/commits/main?ts='+Date.now());if(!/^[a-f0-9]{40}$/.test(head.sha))throw new Error('Invalid SHA');base=`https://raw.githubusercontent.com/ZunchiLab/KBA/${head.sha}/`;origin='GitHub最新コミット';}
      catch (_){base=new URL('../',location.href).href;origin='公開サイトの保存データ（最新コミット確認不可）';}
      const outcomes=await Promise.allSettled(config.venues.map(async v=>{const versionPath=config.version==='v1'?'':config.version+'/';const path=`data/results/nar/${config.date}/${versionPath}${v.venue_key}.json`;const data=await getJSON(base+path+'?ts='+Date.now());validate(data,v.venue_key,digest);merge(data,v.venue_key);const confirmed=data.races.filter(r=>r.status==='confirmed').length;const errors=data.races.filter(r=>r.status==='error').length;return v.label+': '+confirmed+'R確定 / 保存 '+data.updated_at.slice(11,19)+' JST'+(errors?' / 公式取得失敗 '+errors+'R':'')+(data.complete?' 全対象確定':'');}));
      const ok=outcomes.filter(x=>x.status==='fulfilled').map(x=>x.value);const failed=outcomes.filter(x=>x.status==='rejected').length;
      status.textContent=origin+' / '+ok.join(' / ')+(failed?` / ${failed}会場の取得に失敗。既知の印・結果を保持しています。`:'');
      for(const v of config.venues){const data=stored[v.venue_key];if(data&&!data.complete&&Date.now()-Date.parse(data.updated_at)>20*60000)status.textContent+=` / ${v.label}は保存更新から20分超。最新結果を取得できていません。`;}
    } catch(e){status.textContent='結果の取得・照合に失敗しました。既知の印・結果は保持しています。 '+e.message;}
    finally{button.disabled=false;}
  }
  button.addEventListener('click',()=>refresh());
  refresh(true);setInterval(()=>refresh(true),120000);
})();
