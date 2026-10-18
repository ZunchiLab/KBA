// Run the actual shipped script against a small DOM and controlled HTTP feed.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const crypto = require('node:crypto');
const script = fs.readFileSync(path.join(__dirname, '../assets/js/jra-day-report.js'), 'utf8');
const now = Date.parse('2026-10-09T20:50:00+09:00');
const clone = x => JSON.parse(JSON.stringify(x));
class Element {
  constructor() { this.textContent='';this.value='';this.disabled=false;this.hidden=false;this.events={};this.dataset={};this.children=[];this.classes=new Set();this.classList={toggle:(k,on)=>on?this.classes.add(k):this.classes.delete(k)}; }
  addEventListener(event, fn) { this.events[event]=fn; }
  setAttribute() {}
  append(...items) { this.children.push(...items);this.textContent+=items.map(x=>typeof x==='string'?x:x.textContent).join(''); }
  replaceChildren() { this.children=[];this.textContent=''; }
}
function common(d){return {schema_version:'kba.results/1',authority:d.authority,date_jst:d.date_jst,venue_key:d.venue_key,forecast_ref:{version:d.forecast_version,sha256:d.forecast_sha256},updated_at:d.updated_at,races:d.races.map(r=>({race_no:r.race,start_at:r.start_at,status:r.status,source:r.source,rows:r.rows,payouts_status:r.payouts_status||{},payouts:r.refunds||[]}))};}
function fixture(plans=[],embeddedDigest=false,thirdVenue=false) {
  const venues=[{venue_key:'tokyo',label:'東京',baba_code:5},{venue_key:'kyoto',label:'京都',baba_code:8}];
  if(thirdVenue)venues.push({venue_key:'niigata',label:'新潟',baba_code:4});
  const forecast={authority:'jra',date_jst:'2026-10-09',forecast_version:'v1'};
  const forecastText=JSON.stringify(forecast)+'\n';
  const digest=crypto.createHash('sha256').update(forecastText).digest('hex');
  const numbers=[...new Set([1,...plans.flatMap(p=>p.tickets.flatMap(t=>t.numbers))])].sort((a,b)=>a-b);
  const config={date:forecast.date_jst,version:'v1',jsonFile:'day.json',venues,budget:{day_limit_yen:3000},races:venues.map(v=>({venue_key:v.venue_key,race:1,race_uid:v.venue_key+'-r1',start_at:new Date(now-3600000).toISOString(),horses:numbers.map(n=>({number:n,name:v.label+'馬'+(n===1?'':n),status_at_snapshot:'running'})),bet_plans:clone(plans)}))};
  if(embeddedDigest)config.forecastSha256=embeddedDigest===true?digest:embeddedDigest;
  const results={};
  for(const v of venues)results[v.venue_key]={authority:'jra',date_jst:config.date,venue_key:v.venue_key,baba_code:v.baba_code,forecast_version:'v1',forecast_sha256:digest,updated_at:new Date(now-60000).toISOString(),refresh_interval_minutes:2,complete:false,races:[{race:1,start_at:new Date(now-3600000).toISOString(),status:'pending',rows:[],refunds:[]}]};
  const nodes={};for(const id of ['day-forecast','day-results','result-status','refresh-results','horse-search','race-filter','empty-state','plan-total'])nodes[id]=new Element();
  nodes['day-forecast'].textContent=JSON.stringify(config);nodes['day-results'].textContent=JSON.stringify(results);nodes['race-filter'].value='all';nodes['result-status'].textContent='保存済み結果';
  const cards=config.races.map(r=>{const c=new Element();c.id=r.race_uid;c.dataset={venue:r.venue_key,start:r.start_at,search:'馬',bets:'false'};c.parts={};for(const selector of ['.clock-state','.race-result-status','.payouts',...r.horses.map(h=>`.horse[data-number="${h.number}"] .horse-finish`),...r.bet_plans.map(p=>`[data-plan-result="${p.plan_id}"]`)])c.parts[selector]=new Element();c.querySelector=s=>{assert(c.parts[s],s);return c.parts[s];};return c;});
  cards.forEach(c=>nodes[c.id]=c);
  const doc={hidden:true,events:{},getElementById:id=>nodes[id],querySelectorAll:s=>s==='.race'?cards:[],createElement:()=>new Element(),addEventListener(event,fn){this.events[event]=fn;},body:new Element()};
  const win={events:{},scrollY:0,addEventListener(event,fn){this.events[event]=fn;},scrollTo(){}};
  const intervals=[];const requests=[];let clock=now;let apiFailure=false;const unavailable=new Set();const rawUnavailable=new Set();
  class Clock extends Date { constructor(...args){super(...(args.length?args:[clock]));}static now(){return clock;} }
  const context={document:doc,window:win,URL,location:new URL('https://zunchilab.github.io/KBA/predictions/day.html?venue=tokyo'),history:{replaceState(){}},localStorage:{getItem:()=>null,setItem(){}},navigator:{},Date:Clock,TextEncoder,AbortController,crypto:crypto.webcrypto,setTimeout:()=>0,clearTimeout(){},setInterval:(fn,ms)=>intervals.push({fn,ms}),console,
    fetch:async url=>{requests.push(url);if(url==='day.json')return{ok:true,text:async()=>forecastText};if(url.includes('api.github.com')){if(apiFailure)throw new Error('API unavailable');return{ok:true,json:async()=>({sha:'a'.repeat(40)})};}const key=venues.find(v=>url.includes('/'+v.venue_key+'.json'))?.venue_key;assert(key,'Unexpected URL '+url);if(unavailable.has(key)||url.includes('raw.githubusercontent.com')&&rawUnavailable.has(key))throw new Error('HTTP outage');return{ok:true,json:async()=>common(clone(results[key]))};}};
  vm.runInNewContext(script, context, {filename:'jra-day-report.js'});
  const flush=async()=>{for(let i=0;i<30;i++)await new Promise(resolve=>setImmediate(resolve));};
  const confirm=key=>{results[key].races[0].status='confirmed';results[key].races[0].rows=config.races.find(r=>r.venue_key===key).horses.map((h,i)=>({number:h.number,name:h.name,finish:i+1}));results[key].complete=true;};
  return {nodes,cards,doc,win,results,requests,intervals,confirm,flush,click:()=>nodes['refresh-results'].events.click(),advance:ms=>clock+=ms,failAPI:()=>apiFailure=true,unavailable,rawUnavailable};
}
let passed=0;
async function test(name, action){await action();passed++;console.log('PASS '+name);}
(async()=>{
  await test('confirmed finishes render for both venues and button is restored',async()=>{const f=fixture();f.confirm('tokyo');f.confirm('kyoto');await f.click();assert.equal(f.cards[0].parts['.horse[data-number="1"] .horse-finish'].textContent,'1着');assert.equal(f.cards[1].parts['.horse[data-number="1"] .horse-finish'].textContent,'1着');assert.match(f.nodes['result-status'].textContent,/東京: 1R確定.*京都: 1R確定.*画面確認/);assert.equal(f.nodes['refresh-results'].disabled,false);});
  await test('API outage uses current main results before the public-site fallback',async()=>{const f=fixture();f.confirm('tokyo');f.failAPI();await f.click();assert.match(f.nodes['result-status'].textContent,/最新コミット確認不可/);assert.equal(f.cards[0].parts['.horse[data-number="1"] .horse-finish'].textContent,'1着');assert(f.requests.some(x=>x.startsWith('https://raw.githubusercontent.com/ZunchiLab/KBA/main/')));});
  await test('raw result outage falls back per venue after successful API lookup',async()=>{const f=fixture();f.confirm('tokyo');f.rawUnavailable.add('tokyo');await f.click();assert.equal(f.cards[0].parts['.horse[data-number="1"] .horse-finish'].textContent,'1着');assert.match(f.nodes['result-status'].textContent,/最新データ配信に失敗/);});
  await test('one venue HTTP failure leaves its known finishes and updates other venue',async()=>{const f=fixture();f.confirm('tokyo');await f.click();f.unavailable.add('tokyo');f.confirm('kyoto');await f.click();assert.equal(f.cards[0].parts['.horse[data-number="1"] .horse-finish'].textContent,'1着');assert.equal(f.cards[1].parts['.horse[data-number="1"] .horse-finish'].textContent,'1着');assert.match(f.nodes['result-status'].textContent,/1会場の取得に失敗/);assert.equal(f.nodes['refresh-results'].disabled,false);});
  await test('older snapshots cannot regress finish or saved timestamp',async()=>{const f=fixture();f.confirm('tokyo');await f.click();f.results.tokyo.updated_at=new Date(now-3600000).toISOString();f.results.tokyo.races[0].status='pending';f.results.tokyo.races[0].rows=[];f.results.tokyo.complete=false;await f.click();assert.equal(f.cards[0].parts['.horse[data-number="1"] .horse-finish'].textContent,'1着');assert.match(f.nodes['result-status'].textContent,/東京: 1R確定 \/ 保存 11:49:00/);});
  await test('newly incomplete response retains confirmed finish',async()=>{const f=fixture();f.confirm('tokyo');await f.click();f.results.tokyo.updated_at=new Date(now).toISOString();f.results.tokyo.races[0].status='pending';f.results.tokyo.races[0].rows=[];f.results.tokyo.complete=false;await f.click();assert.equal(f.cards[0].parts['.horse[data-number="1"] .horse-finish'].textContent,'1着');});
  await test('wrong date, venue, hash and horse identity are rejected',async()=>{for(const mutation of [d=>d.authority='nar',d=>d.date_jst='2026-10-08',d=>d.venue_key='other',d=>d.forecast_sha256='bad',d=>d.races[0].rows[0].name='他の馬',d=>d.races[0].rows=[],d=>d.updated_at='invalid']){const f=fixture();f.confirm('tokyo');await f.click();mutation(f.results.tokyo);await f.click();assert.equal(f.cards[0].parts['.horse[data-number="1"] .horse-finish'].textContent,'1着');assert.match(f.nodes['result-status'].textContent,/取得に失敗/);}});
  await test('stalled due results show warning after three collection intervals',async()=>{const f=fixture();await f.click();f.advance(6*60000);f.intervals.find(x=>x.ms===30000&&x.fn.name==='showRefreshStatus').fn();assert.match(f.nodes['result-status'].textContent,/保存更新から6分超/);assert(f.nodes['result-status'].classes.has('update-warning'));});
  await test('future races and completed venues do not show stale warning',async()=>{const f=fixture();for(const d of Object.values(f.results)){d.updated_at=new Date(now-3600000).toISOString();d.races[0].start_at=new Date(now+3600000).toISOString();}await f.click();assert.doesNotMatch(f.nodes['result-status'].textContent,/停止している可能性/);f.confirm('tokyo');f.confirm('kyoto');await f.click();assert.doesNotMatch(f.nodes['result-status'].textContent,/停止している可能性/);});
  await test('returning from hidden mobile tab immediately refreshes',async()=>{const f=fixture();await f.click();f.advance(10000);f.confirm('tokyo');const before=f.requests.length;f.doc.hidden=false;f.doc.events.visibilitychange();await f.flush();assert(f.requests.length>before);assert.equal(f.cards[0].parts['.horse[data-number="1"] .horse-finish'].textContent,'1着');});
  await test('pageshow and focus resume events refresh without waiting two minutes',async()=>{for(const event of ['pageshow','focus']){const f=fixture();await f.click();f.advance(10000);f.confirm('tokyo');f.doc.hidden=false;f.win.events[event]();await f.flush();assert.equal(f.cards[0].parts['.horse[data-number="1"] .horse-finish'].textContent,'1着');}});
  await test('completed page stops automatic polling but manual refresh remains available',async()=>{const f=fixture();f.confirm('tokyo');f.confirm('kyoto');await f.click();f.doc.hidden=false;const before=f.requests.length;f.intervals.find(x=>x.ms===120000).fn();await f.flush();assert.equal(f.requests.length,before);await f.click();assert(f.requests.length>before);});
  const formationPlan=value=>({plan_id:'formation',type:'馬連',kind:'quinella',ordered:false,all_points_price_condition_at_snapshot:value===true,tickets:[[1,2],[1,3],[1,4],[2,3],[2,4]].map((numbers,i)=>({numbers,example_stake_yen:100,price_condition_at_snapshot:i===0?value:true}))});
  await test('one failed or missing point skips the complete formation',async()=>{for(const value of [false,null]){const f=fixture([formationPlan(value)]);f.confirm('tokyo');f.results.tokyo.races[0].refunds=[{kind:'quinella',numbers:[1,3],yen_per_100:1000}];await f.click();const text=f.cards[0].parts['[data-plan-result="formation"]'].textContent;assert.match(text,/構成全点を見送り/);assert.doesNotMatch(text,/400円|点的中/);}});
  await test('all eligible formation points use the complete cost and official payout',async()=>{const f=fixture([formationPlan(true)]);f.confirm('tokyo');f.results.tokyo.races[0].refunds=[{kind:'quinella',numbers:[1,2],yen_per_100:1000}];await f.click();assert.match(f.cards[0].parts['[data-plan-result="formation"]'].textContent,/1\/5点的中、500円→1000円/);});
  await test('historical per-ticket price semantics stay unchanged',async()=>{const p=formationPlan(false);delete p.all_points_price_condition_at_snapshot;const f=fixture([p]);f.confirm('tokyo');f.results.tokyo.races[0].refunds=[{kind:'quinella',numbers:[1,3],yen_per_100:1000}];await f.click();assert.match(f.cards[0].parts['[data-plan-result="formation"]'].textContent,/1\/4点的中、400円→1000円/);});
  await test('server-verified embedded digest avoids the large forecast download',async()=>{const f=fixture([],true);f.confirm('tokyo');await f.click();assert.equal(f.cards[0].parts['.horse[data-number="1"] .horse-finish'].textContent,'1着');assert(!f.requests.includes('day.json'));});
  await test('embedded digest still rejects a mismatched result hash',async()=>{const f=fixture([],true);f.confirm('tokyo');await f.click();f.results.tokyo.forecast_sha256='b'.repeat(64);await f.click();assert.match(f.nodes['result-status'].textContent,/取得に失敗/);assert.equal(f.cards[0].parts['.horse[data-number="1"] .horse-finish'].textContent,'1着');});
  await test('invalid embedded digest keeps the legacy JSON verification',async()=>{const f=fixture([],'bad');f.confirm('tokyo');await f.click();assert(f.requests.includes('day.json'));assert.equal(f.cards[0].parts['.horse[data-number="1"] .horse-finish'].textContent,'1着');});
  await test('both API and raw main outages still use the public-site saved data',async()=>{const f=fixture();f.confirm('tokyo');f.failAPI();f.rawUnavailable.add('tokyo');await f.click();assert.equal(f.cards[0].parts['.horse[data-number="1"] .horse-finish'].textContent,'1着');assert.match(f.nodes['result-status'].textContent,/公開サイトの保存結果/);assert(f.requests.some(x=>x.startsWith('https://zunchilab.github.io/KBA/data/')));});
  await test('Niigata common results validate as official venue 04 and update beside Tokyo/Kyoto',async()=>{const f=fixture([],true,true);f.confirm('niigata');await f.click();assert.equal(f.cards[2].parts['.horse[data-number="1"] .horse-finish'].textContent,'1着');assert.match(f.nodes['result-status'].textContent,/新潟: 1R確定/);});
  await test('all eight payout types are visible with ordered arrows and bracket labels',async()=>{
    const f=fixture([formationPlan(true)]);f.confirm('tokyo');
    f.results.tokyo.races[0].refunds=[{kind:'win',numbers:[3],yen_per_100:1550},{kind:'place',numbers:[3],yen_per_100:220},{kind:'place',numbers:[1],yen_per_100:120},{kind:'bracket_quinella',numbers:[1,3],yen_per_100:390},{kind:'quinella',numbers:[1,3],yen_per_100:1190},{kind:'wide',numbers:[1,3],yen_per_100:390},{kind:'exacta',numbers:[3,1],yen_per_100:4180},{kind:'trio',numbers:[1,2,3],yen_per_100:1150},{kind:'trifecta',numbers:[3,1,2],yen_per_100:17820}];
    await f.click();const details=f.cards[0].parts['.payouts'].children[0];assert.equal(details.open,true);
    const body=details.children.find(e=>e.className==='payout-table').children[1];assert.equal(body.children.length,8);
    const text=details.textContent;for(const name of ['単勝','複勝','枠連（枠番）','馬連','ワイド','馬単','三連複','三連単'])assert(text.includes(name));
    assert.match(text,/3→1.*4,180円/);assert.match(text,/3→1→2.*17,820円/);
    assert.equal(body.children.find(e=>e.dataset.kind==='place').children[1].children.length,2);
  });
  await test('payout refresh preserves a manually closed table and all known results during outages',async()=>{
    const f=fixture();f.confirm('tokyo');f.results.tokyo.races[0].refunds=[{kind:'win',numbers:[1],yen_per_100:250}];await f.click();
    f.cards[0].parts['.payouts'].children[0].open=false;await f.click();assert.equal(f.cards[0].parts['.payouts'].children[0].open,false);
    f.unavailable.add('tokyo');await f.click();assert.match(f.cards[0].parts['.payouts'].textContent,/250円/);
  });
  await test('missing payouts stay pending and explicit unavailable bet types stay distinct',async()=>{
    const f=fixture();f.confirm('tokyo');f.results.tokyo.races[0].payouts_status={bracket_quinella:'not_offered'};await f.click();
    const text=f.cards[0].parts['.payouts'].textContent;assert.match(text,/発売なし/);assert.match(text,/未掲載・確認待ち/);assert.doesNotMatch(text,/(^|\D)0円/);
  });
  await test('unrelated non-finishers do not block verified tickets and affected tickets stay on hold',async()=>{
    const plan=(id,nums)=>({plan_id:id,type:'ワイド',ordered:false,tickets:[{numbers:nums,example_stake_yen:100,price_condition_at_snapshot:true}]});
    const f=fixture([plan('unaffected',[1,2]),plan('affected',[1,3])]);f.confirm('tokyo');f.results.tokyo.races[0].rows.find(r=>r.number===3).finish='除外';
    f.results.tokyo.races[0].refunds=[{kind:'wide',numbers:[1,2],yen_per_100:300}];await f.click();
    assert.match(f.cards[0].parts['[data-plan-result="unaffected"]'].textContent,/1\/1点的中、100円→300円/);
    assert.match(f.cards[0].parts['[data-plan-result="affected"]'].textContent,/対象買い目.*照合待ち/);
  });
  console.log(passed+' UI regression cases passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
