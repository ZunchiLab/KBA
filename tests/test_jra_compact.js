// Exercise the shipped navigation with a controlled DOM; no HTTP or wagers.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
class Element{
  constructor(){this.dataset={};this.attrs={};this.value='';this.textContent='';this.events={};this.hidden=false;this.children=[];this.classList={toggle(){}};}
  setAttribute(k,v){this.attrs[k]=v;}
  getAttribute(k){return this.attrs[k];}
  addEventListener(k,fn){this.events[k]=fn;}
  append(...items){this.children.push(...items);}
  focus(){}
}
function fixture(url='https://zunchilab.github.io/KBA/predictions/test.html?venue=tokyo',thirdVenue=false){
  const location=new URL(url),venues=[{venue_key:'tokyo',label:'東京',baba_code:5},{venue_key:'kyoto',label:'京都',baba_code:8}];
  if(thirdVenue)venues.push({venue_key:'niigata',label:'新潟',baba_code:4});
  const config={compact:true,date:'2026-10-12',version:'v1',venues,budget:{day_limit_yen:3000},races:venues.flatMap(v=>[1,2].map(n=>({race:n,race_uid:`jra-2026-10-12-${v.venue_key}-r${n}`,venue_key:v.venue_key,start_at:'2026-10-12T10:00:00+09:00',horses:[],bet_plans:[]})))};
  const nodes=Object.fromEntries(['day-forecast','day-results','horse-search','race-filter','empty-state','plan-total','result-status','refresh-results'].map(k=>[k,new Element()]));
  nodes['day-forecast'].textContent=JSON.stringify(config);nodes['day-results'].textContent='{}';nodes['race-filter'].value='all';
  const tabs=venues.map(v=>{const e=new Element();e.dataset.venue=v.venue_key;return e;});
  const panels=venues.map(v=>{const e=new Element();e.id='venue-'+v.venue_key;return e;});
  const jumps=venues.map(v=>{const e=new Element();e.dataset.venue=v.venue_key;return e;});
  const cards=config.races.map(r=>{const e=new Element();e.id=r.race_uid;e.dataset={venue:r.venue_key,start:r.start_at,search:r.race===1?'alpha':'beta',bets:String(r.race===2)};e.clock=new Element();e.querySelector=()=>e.clock;return e;});
  const links=config.races.map(r=>{const e=new Element();e.dataset.raceUid=r.race_uid;e.attrs.href='#'+r.race_uid;e.closest=()=>jumps.find(j=>j.dataset.venue===r.venue_key);return e;});
  const selectors={'[role=tab]':tabs,'.venue-panel':panels,'.race':cards,'.sticky .race-jumps':jumps,'.race-jumps a[data-race-uid]':links,'a[href^="#jra-"]':links};
  const window={events:{},scrollY:0,addEventListener(k,fn){this.events[k]=fn;},scrollTo(){}};
  const doc={hidden:true,getElementById:k=>nodes[k],querySelectorAll:s=>selectors[s]||[],addEventListener(){}};
  const history={replaceState(_a,_b,u){location.href=u.href;}};
  const context={document:doc,window,URL,location,history,localStorage:{getItem:()=>null,setItem(){}},Date,console,setInterval(){},setTimeout(){},navigator:{}};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../assets/js/jra-day-report.js'),'utf8'),context);
  const visible=()=>cards.filter(c=>!c.hidden&&panels.some(p=>p.id==='venue-'+c.dataset.venue&&!p.hidden)).map(c=>c.id);
  const navigate=n=>{const a=links[n];let prevented=false;a.events.click({preventDefault(){prevented=true;}});if(!prevented){location.hash=a.attrs.href;window.events.hashchange();}return prevented;};
  return {nodes,tabs,panels,cards,links,location,visible,navigate};
}
let n=0;
function test(label,fn){fn();n++;console.log('PASS '+label);}
test('default displays exactly one race and stores its URL',()=>{const f=fixture();assert.deepEqual(f.visible(),['jra-2026-10-12-tokyo-r1']);assert.equal(f.location.hash,'#jra-2026-10-12-tokyo-r1');});
test('deep link selects its venue and race',()=>{const f=fixture('https://zunchilab.github.io/KBA/predictions/test.html#jra-2026-10-12-kyoto-r2');assert.deepEqual(f.visible(),['jra-2026-10-12-kyoto-r2']);});
test('jump selects one race and marks its button',()=>{const f=fixture();f.navigate(1);assert.deepEqual(f.visible(),['jra-2026-10-12-tokyo-r2']);assert.equal(f.links[1].attrs['aria-current'],'true');});
test('venue switch remembers each selected race',()=>{const f=fixture();f.navigate(1);f.tabs[1].events.click();f.navigate(3);f.tabs[0].events.click();assert.deepEqual(f.visible(),['jra-2026-10-12-tokyo-r2']);assert.equal(f.location.hash,'#jra-2026-10-12-tokyo-r2');f.tabs[1].events.click();assert.deepEqual(f.visible(),['jra-2026-10-12-kyoto-r2']);});
test('main-only filter selects a matching race and blocks excluded jumps',()=>{const f=fixture();f.nodes['race-filter'].value='buy';f.nodes['race-filter'].events.change();assert.deepEqual(f.visible(),['jra-2026-10-12-tokyo-r2']);assert.equal(f.navigate(0),true);});
test('search selects its matching race without stale hash',()=>{const f=fixture();f.nodes['horse-search'].value='beta';f.nodes['horse-search'].events.input();assert.deepEqual(f.visible(),['jra-2026-10-12-tokyo-r2']);assert.equal(f.location.hash,'#jra-2026-10-12-tokyo-r2');});
test('no match displays empty state and preserves the data',()=>{const f=fixture();f.nodes['horse-search'].value='not found';f.nodes['horse-search'].events.input();assert.deepEqual(f.visible(),[]);assert.equal(f.nodes['empty-state'].hidden,false);assert.equal(f.cards.length,4);});
test('search and filter are preserved separately per venue',()=>{const f=fixture();f.nodes['horse-search'].value='beta';f.nodes['horse-search'].events.input();f.tabs[1].events.click();assert.equal(f.nodes['horse-search'].value,'');f.tabs[0].events.click();assert.equal(f.nodes['horse-search'].value,'beta');assert.deepEqual(f.visible(),['jra-2026-10-12-tokyo-r2']);});
test('Niigata deep link and three-venue switching keep the selected race',()=>{const f=fixture('https://zunchilab.github.io/KBA/predictions/test.html#jra-2026-10-12-niigata-r2',true);assert.deepEqual(f.visible(),['jra-2026-10-12-niigata-r2']);f.tabs[0].events.click();f.tabs[2].events.click();assert.deepEqual(f.visible(),['jra-2026-10-12-niigata-r2']);assert.equal(f.cards.length,6);});
console.log(n+' compact navigation cases passed');
