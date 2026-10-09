// Run the actual shipped script against a small DOM and controlled HTTP feed.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const crypto = require('node:crypto');
const script = fs.readFileSync(path.join(__dirname, '../assets/js/day-report.js'), 'utf8');
const now = Date.parse('2026-10-09T20:50:00+09:00');
const clone = x => JSON.parse(JSON.stringify(x));
class Element {
  constructor() { this.textContent='';this.value='';this.disabled=false;this.hidden=false;this.events={};this.dataset={};this.children=[];this.classes=new Set();this.classList={toggle:(k,on)=>on?this.classes.add(k):this.classes.delete(k)}; }
  addEventListener(event, fn) { this.events[event]=fn; }
  setAttribute() {}
  append(...items) { this.children.push(...items);this.textContent+=items.map(x=>typeof x==='string'?x:x.textContent).join(''); }
  replaceChildren() { this.children=[];this.textContent=''; }
}
function fixture() {
  const venues=[{venue_key:'sonoda',label:'園田',baba_code:27},{venue_key:'ooi',label:'大井',baba_code:20}];
  const forecast={date_jst:'2026-10-09',forecast_version:'v1'};
  const forecastText=JSON.stringify(forecast)+'\n';
  const digest=crypto.createHash('sha256').update(forecastText).digest('hex');
  const config={date:forecast.date_jst,version:'v1',jsonFile:'day.json',venues,budget:{day_limit_yen:3000},races:venues.map(v=>({venue_key:v.venue_key,race:1,race_uid:v.venue_key+'-r1',start_at:new Date(now-3600000).toISOString(),horses:[{number:1,name:v.label+'馬',status_at_snapshot:'running'}],bet_plans:[]}))};
  const results={};
  for(const v of venues)results[v.venue_key]={date_jst:config.date,venue_key:v.venue_key,baba_code:v.baba_code,forecast_version:'v1',forecast_sha256:digest,updated_at:new Date(now-60000).toISOString(),refresh_interval_minutes:2,complete:false,races:[{race:1,start_at:new Date(now-3600000).toISOString(),status:'pending',rows:[],refunds:[]}]};
  const nodes={};for(const id of ['day-forecast','day-results','result-status','refresh-results','horse-search','race-filter','empty-state','plan-total'])nodes[id]=new Element();
  nodes['day-forecast'].textContent=JSON.stringify(config);nodes['day-results'].textContent=JSON.stringify(results);nodes['race-filter'].value='all';nodes['result-status'].textContent='保存済み結果';
  const cards=config.races.map(r=>{const c=new Element();c.id=r.race_uid;c.dataset={venue:r.venue_key,start:r.start_at,search:'馬',bets:'false'};c.parts={};for(const selector of ['.clock-state','.race-result-status','.payouts','.horse[data-number="1"] .horse-finish'])c.parts[selector]=new Element();c.querySelector=s=>{assert(c.parts[s],s);return c.parts[s];};return c;});
  cards.forEach(c=>nodes[c.id]=c);
  const doc={hidden:true,events:{},getElementById:id=>nodes[id],querySelectorAll:s=>s==='.race'?cards:[],createElement:()=>new Element(),addEventListener(event,fn){this.events[event]=fn;},body:new Element()};
  const win={events:{},scrollY:0,addEventListener(event,fn){this.events[event]=fn;},scrollTo(){}};
  const intervals=[];const requests=[];let clock=now;let apiFailure=false;const unavailable=new Set();const rawUnavailable=new Set();
  class Clock extends Date { constructor(...args){super(...(args.length?args:[clock]));}static now(){return clock;} }
  const context={document:doc,window:win,URL,location:new URL('https://zunchilab.github.io/KBA/predictions/day.html?venue=sonoda'),history:{replaceState(){}},localStorage:{getItem:()=>null,setItem(){}},navigator:{},Date:Clock,TextEncoder,AbortController,crypto:crypto.webcrypto,setTimeout:()=>0,clearTimeout(){},setInterval:(fn,ms)=>intervals.push({fn,ms}),console,
    fetch:async url=>{requests.push(url);if(url==='day.json')return{ok:true,text:async()=>forecastText};if(url.includes('api.github.com')){if(apiFailure)throw new Error('API unavailable');return{ok:true,json:async()=>({sha:'a'.repeat(40)})};}const key=venues.find(v=>url.includes('/'+v.venue_key+'.json'))?.venue_key;assert(key,'Unexpected URL '+url);if(unavailable.has(key)||url.includes('raw.githubusercontent.com')&&rawUnavailable.has(key))throw new Error('HTTP outage');return{ok:true,json:async()=>clone(results[key])};}};
  vm.runInNewContext(script, context, {filename:'day-report.js'});
  const flush=async()=>{for(let i=0;i<30;i++)await new Promise(resolve=>setImmediate(resolve));};
  const confirm=key=>{results[key].races[0].status='confirmed';results[key].races[0].rows=[{number:1,name:venues.find(v=>v.venue_key===key).label+'馬',finish:1}];results[key].complete=true;};
  return {nodes,cards,doc,win,results,requests,intervals,confirm,flush,click:()=>nodes['refresh-results'].events.click(),advance:ms=>clock+=ms,failAPI:()=>apiFailure=true,unavailable,rawUnavailable};
}
let passed=0;
async function test(name, action){await action();passed++;console.log('PASS '+name);}
(async()=>{
  await test('confirmed finishes render for both venues and button is restored',async()=>{const f=fixture();f.confirm('sonoda');f.confirm('ooi');await f.click();assert.equal(f.cards[0].parts['.horse[data-number="1"] .horse-finish'].textContent,'1着');assert.equal(f.cards[1].parts['.horse[data-number="1"] .horse-finish'].textContent,'1着');assert.match(f.nodes['result-status'].textContent,/園田: 1R確定.*大井: 1R確定.*画面確認/);assert.equal(f.nodes['refresh-results'].disabled,false);});
  await test('API outage uses public-site fallback',async()=>{const f=fixture();f.confirm('sonoda');f.failAPI();await f.click();assert.match(f.nodes['result-status'].textContent,/最新コミット確認不可/);assert.equal(f.cards[0].parts['.horse[data-number="1"] .horse-finish'].textContent,'1着');assert(f.requests.some(x=>x.startsWith('https://zunchilab.github.io/KBA/data/')));});
  await test('raw result outage falls back per venue after successful API lookup',async()=>{const f=fixture();f.confirm('sonoda');f.rawUnavailable.add('sonoda');await f.click();assert.equal(f.cards[0].parts['.horse[data-number="1"] .horse-finish'].textContent,'1着');assert.match(f.nodes['result-status'].textContent,/最新データ配信に失敗/);});
  await test('one venue HTTP failure leaves its known finishes and updates other venue',async()=>{const f=fixture();f.confirm('sonoda');await f.click();f.unavailable.add('sonoda');f.confirm('ooi');await f.click();assert.equal(f.cards[0].parts['.horse[data-number="1"] .horse-finish'].textContent,'1着');assert.equal(f.cards[1].parts['.horse[data-number="1"] .horse-finish'].textContent,'1着');assert.match(f.nodes['result-status'].textContent,/1会場の取得に失敗/);assert.equal(f.nodes['refresh-results'].disabled,false);});
  await test('older snapshots cannot regress finish or saved timestamp',async()=>{const f=fixture();f.confirm('sonoda');await f.click();f.results.sonoda.updated_at=new Date(now-3600000).toISOString();f.results.sonoda.races[0].status='pending';f.results.sonoda.races[0].rows=[];f.results.sonoda.complete=false;await f.click();assert.equal(f.cards[0].parts['.horse[data-number="1"] .horse-finish'].textContent,'1着');assert.match(f.nodes['result-status'].textContent,/園田: 1R確定 \/ 保存 11:49:00/);});
  await test('newly incomplete response retains confirmed finish',async()=>{const f=fixture();f.confirm('sonoda');await f.click();f.results.sonoda.updated_at=new Date(now).toISOString();f.results.sonoda.races[0].status='pending';f.results.sonoda.races[0].rows=[];f.results.sonoda.complete=false;await f.click();assert.equal(f.cards[0].parts['.horse[data-number="1"] .horse-finish'].textContent,'1着');});
  await test('wrong date, venue, hash and horse identity are rejected',async()=>{for(const mutation of [d=>d.date_jst='2026-10-08',d=>d.venue_key='other',d=>d.forecast_sha256='bad',d=>d.races[0].rows[0].name='他の馬',d=>d.races[0].rows=[],d=>d.updated_at='invalid']){const f=fixture();f.confirm('sonoda');await f.click();mutation(f.results.sonoda);await f.click();assert.equal(f.cards[0].parts['.horse[data-number="1"] .horse-finish'].textContent,'1着');assert.match(f.nodes['result-status'].textContent,/取得に失敗/);}});
  await test('stalled due results show warning after three collection intervals',async()=>{const f=fixture();await f.click();f.advance(6*60000);f.intervals.find(x=>x.ms===30000&&x.fn.name==='showRefreshStatus').fn();assert.match(f.nodes['result-status'].textContent,/保存更新から6分超/);assert(f.nodes['result-status'].classes.has('update-warning'));});
  await test('future races and completed venues do not show stale warning',async()=>{const f=fixture();for(const d of Object.values(f.results)){d.updated_at=new Date(now-3600000).toISOString();d.races[0].start_at=new Date(now+3600000).toISOString();}await f.click();assert.doesNotMatch(f.nodes['result-status'].textContent,/停止している可能性/);f.confirm('sonoda');f.confirm('ooi');await f.click();assert.doesNotMatch(f.nodes['result-status'].textContent,/停止している可能性/);});
  await test('returning from hidden mobile tab immediately refreshes',async()=>{const f=fixture();await f.click();f.advance(10000);f.confirm('sonoda');const before=f.requests.length;f.doc.hidden=false;f.doc.events.visibilitychange();await f.flush();assert(f.requests.length>before);assert.equal(f.cards[0].parts['.horse[data-number="1"] .horse-finish'].textContent,'1着');});
  await test('pageshow and focus resume events refresh without waiting two minutes',async()=>{for(const event of ['pageshow','focus']){const f=fixture();await f.click();f.advance(10000);f.confirm('sonoda');f.doc.hidden=false;f.win.events[event]();await f.flush();assert.equal(f.cards[0].parts['.horse[data-number="1"] .horse-finish'].textContent,'1着');}});
  await test('completed page stops automatic polling but manual refresh remains available',async()=>{const f=fixture();f.confirm('sonoda');f.confirm('ooi');await f.click();f.doc.hidden=false;const before=f.requests.length;f.intervals.find(x=>x.ms===120000).fn();await f.flush();assert.equal(f.requests.length,before);await f.click();assert(f.requests.length>before);});
  console.log(passed+' UI regression cases passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
