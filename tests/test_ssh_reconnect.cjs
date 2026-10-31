const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
class Element{
  constructor(){this.value='';this.checked=true;this.children=[];this.dataset={};this.style={setProperty(){}};this.classList={toggle(){},add(){},remove(){}};this.listeners={};}
  append(...items){this.children.push(...items);}
  replaceChildren(...items){this.children=items;}
  get childElementCount(){return this.children.length;}
  setAttribute(){} removeAttribute(){} contains(){return false;}
}
const elements={},get=id=>elements[id]??=new Element(),events={},calls=[];
let connected=false,healthy=true,failure=null,now=100000,interval;
const profile={host:'vm.test',username:'driver',port:22,auto_connect:true};
const status=()=>({connected,profile,identity:connected?profile:null,directories:[]});
const context={
  $,state:{busy:false,preview:null,track:null},
  document:{hidden:false,activeElement:null,body:{classList:{remove(){}}},querySelector:()=>get('connection'),querySelectorAll:()=>[],createElement:()=>new Element(),createElementNS:()=>new Element(),addEventListener:(name,fn)=>events[name]=fn},
  window:{addEventListener:(name,fn)=>events[name]=fn,i18n:{confirm:()=>true}},
  fetch:async(url,options)=>{
    const action=url.split('/').pop();calls.push(action);
    if(action==='health'&&!healthy)connected=false;
    if(action==='connect'){
      if(failure)return {ok:false,status:failure.status||400,json:async()=>failure};
      connected=true;healthy=true;
    }
    if(action==='disconnect'||action==='forget')connected=false;
    return {ok:true,status:200,json:async()=>action==='list'?{path:'/home/driver',entries:[]}:status()};
  },
  Date:{now:()=>now},setInterval:fn=>interval=fn,FormData,draw(){},say(){},busy(){},loadTrack(){},console,
};
function $(id){return get(id);}
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../raceline_studio/static/remote.js'),'utf8'),context);
const settle=async()=>{for(let i=0;i<8;i++)await new Promise(resolve=>setImmediate(resolve));};
(async()=>{
  await settle();assert.equal(connected,true,'page load auto-connects');
  assert.equal(get('sshHost').value,'vm.test');
  get('connection').open=true;await interval();await settle();
  assert.equal(get('connection').open,true,'health polling keeps connection settings open');
  healthy=false;await interval();await settle();
  assert.equal(connected,true,'broken file channel reconnects');
  const connects=()=>calls.filter(v=>v==='connect').length;
  await get('sshDisconnect').onclick();const before=connects();await interval();await settle();
  assert.equal(connected,false);assert.equal(connects(),before,'intentional disconnect stays disconnected');
  await get('sshConnect').onclick();assert.equal(connected,true,'manual connection still works');
  healthy=false;failure={error:'offline'};await interval();await settle();const attempts=connects();
  await interval();await settle();assert.equal(connects(),attempts,'backoff avoids repeated logins');
  now+=61000;failure=null;await events.focus();await settle();assert.equal(connected,true,'focus restores expired session');
  healthy=false;failure={reason:'keychain_read',error:'enter password'};now+=61000;
  await interval();await settle();const lockedAttempts=connects();now+=61000;await interval();await settle();
  assert.equal(connects(),lockedAttempts,'credential failures wait for user input');
  failure=null;await get('sshConnect').onclick();assert.equal(connected,true);
  assert.equal(calls.includes('save'),false,'recovery never retries writes');
  console.log('SSH reconnect checks passed: startup, dead SFTP, manual reconnect, intentional disconnect, backoff, wake, credential failure, no write retries.');
})().catch(error=>{console.error(error);process.exitCode=1;});
