const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
class E{constructor(){this.dataset={};this.value='';this.textContent='';this.attrs={};this.events={};this.children=[];this.classList={toggle(){}};}setAttribute(k,v){this.attrs[k]=v;}addEventListener(k,v){this.events[k]=v;}append(h){this.children=this.children.filter(x=>x!==h);this.children.push(h);}focus(){}}
const ids=Object.fromEntries(['day-forecast','day-results','horse-search','race-filter','empty-state','plan-total','result-status','refresh-results'].map(k=>[k,new E()]));
const config={compact:true,date:'2026-11-01',version:'test',venues:[{venue_key:'tokyo'}],budget:{day_limit_yen:0},races:[{race_uid:'jra-2026-11-01-tokyo-r1',venue_key:'tokyo',race:1,bet_plans:[],horses:[]}]};
ids['day-forecast'].textContent=JSON.stringify(config);ids['day-results'].textContent='{}';ids['race-filter'].value='all';
const card=new E(),clock=new E(),list=new E(),select=new E(),panel=new E();card.id=config.races[0].race_uid;card.dataset={venue:'tokyo',start:'2026-11-01T10:00:00+09:00',search:'test',bets:'false'};card.querySelector=s=>s==='.all-horses'?list:clock;panel.id='venue-tokyo';select.closest=()=>card;
const input=[[1,1,10,30,80,20,40],[2,2,90,90,10,80,60],[3,3,60,60,70,90,20],[4,4,null,null,null,null,null],[5,5,70,60,30,50,90],[6,null,100,100,100,100,100]];
list.children=input.map(([number,rank,score,first,second,top2,top3])=>{const e=new E();e.open=number===1;e.dataset=Object.fromEntries(Object.entries({number,rank,score,first,second,top2,top3,inactive:number===6}).map(([k,v])=>[k,v===null?'':String(v)]));return e;});
const selectors={'.race':[card],'.venue-panel':[panel],'.horse-sort':[select]};const doc={hidden:true,getElementById:k=>ids[k],querySelectorAll:s=>selectors[s]||[],addEventListener(){}};
const location=new URL('https://zunchilab.github.io/KBA/tools/test.html');const context={document:doc,window:{scrollY:0,addEventListener(){},scrollTo(){}},URL,location,history:{replaceState(_a,_b,u){location.href=u.href;}},localStorage:{getItem:()=>null,setItem(){}},Date,console,setInterval(){},setTimeout(){},navigator:{}};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../assets/js/jra-day-report.js'),'utf8'),context);
const initial=ids['day-forecast'].textContent,opened=list.children[0];
for(const [key,expected] of Object.entries({first:[2,3,5,1,4,6],second:[1,3,5,2,4,6],top2:[3,2,5,1,4,6],top3:[5,2,1,3,4,6],score:[2,5,3,1,4,6],number:[1,2,3,4,5,6],rank:[1,2,3,4,5,6]})){
 select.value=key;select.events.change();assert.deepEqual(list.children.map(e=>Number(e.dataset.number)),expected,key);assert.equal(list.children.length,6);assert.equal(opened.open,true);assert.equal(ids['day-forecast'].textContent,initial);console.log('PASS '+key+' sorting, ties, nulls, withdrawn, details and frozen data');
}
