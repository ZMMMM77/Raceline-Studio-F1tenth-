const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
class Element {
  constructor(){this.listeners={};this.children=[];this.hidden=false;this.disabled=false;this.value='map';this.classList={toggle(){}};this.attrs={};}
  addEventListener(type,fn){(this.listeners[type]??=[]).push(fn);}
  setAttribute(name,value){this.attrs[name]=value;}
  replaceChildren(){this.children=[];} append(item){this.children.push(item);}
  getBoundingClientRect(){return{left:20,top:30};}
}
const elements={},get=id=>elements[id]??=new Element(),events={},calls=[];
let stored={zones:[],revision:'0',key:'map'},failure=false,delay=null;
const state={track:{id:'track',exclusions:stored},busy:false,preview:null,result:null};
const view={s:20,cx:2,cy:3,x:200,y:150,screen:p=>[200+(p[0]-2)*20,150-(p[1]-3)*20]};
const ctx=new Proxy({}, {get:()=>()=>{},set:()=>true});
const context={$,state,document:{createElement:()=>new Element(),addEventListener:(type,fn)=>events[type]=fn},
  window:{i18n:{t:v=>v},addEventListener(){},waypointEditor:{active:false}},
  draw:()=>context.window.exclusionEditor?.paint(ctx,view.screen,view),say:()=>{},
  fetch:async(url,options)=>{const request=JSON.parse(options.body);calls.push({url,request});if(delay)await delay;
    if(failure)return{ok:false,status:400,json:async()=>({error:'invalid polygon'})};
    if(request.revision!==stored.revision)return{ok:false,status:409,json:async()=>({error:'conflict',current:stored})};
    stored={zones:request.zones,revision:String(+stored.revision+1),key:'map'};return{ok:true,json:async()=>stored};}};
function $(id){return get(id);}
vm.createContext(context);vm.runInContext(fs.readFileSync(path.join(__dirname,'../raceline_studio/static/exclusions.js'),'utf8'),context);
const editor=context.window.exclusionEditor;
function event(world,props={}){const q=view.screen(world);return{clientX:q[0]+20,clientY:q[1]+30,button:0,target:{closest:()=>false},preventDefault(){this.prevented=true;},stopImmediatePropagation(){this.stopped=true;},...props};}
function emit(type,e){for(const fn of get('trackCanvas').listeners[type]||[]){fn(e);if(e.stopped)break;}return e;}
const click=(p,props)=>emit('pointerdown',event(p,props));
const tick=()=>new Promise(resolve=>setImmediate(resolve));
const points=[[2,3],[4,3],[4,5],[2,5]];
function startPolygon(){get('exclusionToggle').onclick();get('exclusionAdd').onclick();context.draw();points.forEach(p=>click(p));}
(async()=>{
  editor.load(state.track);context.draw();
  assert.equal(click([0,0],{ctrlKey:true}).stopped,undefined,'closed tool must not swallow Ctrl selection');
  startPolygon();assert.equal(get('optimize').disabled,true);assert.equal(editor.ready(),false);
  await get('exclusionFinish').onclick();
  assert.deepEqual(stored.zones,[points],'screen transform must preserve world metres despite pan/zoom');
  assert.equal(editor.ready(),true);assert.equal(get('optimize').disabled,false);
  assert.equal(calls[0].request.revision,'0');
  await get('exclusionDelete').onclick();assert.deepEqual(stored.zones,[]);
  await get('exclusionUndo').onclick();assert.deepEqual(stored.zones,[points]);
  // Repeated clicks cannot issue concurrent saves, and drawing blocks other handlers.
  get('exclusionAdd').onclick();context.draw();points.forEach(p=>click(p.map(v=>v+5)));
  assert.equal(click([10,10],{ctrlKey:true}).stopped,true);
  let release;delay=new Promise(resolve=>release=resolve);const saving=get('exclusionFinish').onclick();
  const count=calls.length;await get('exclusionFinish').onclick();assert.equal(calls.length,count);
  assert.equal(get('optimize').disabled,true);release();await saving;delay=null;
  assert.equal(editor.ready(),true);
  get('exclusionAdd').onclick();click([1,1]);
  const escape=event([0,0],{key:'Escape'});events.keydown(escape);
  assert.equal(escape.stopped,true);assert.equal(editor.ready(),true);
  // Failed validation keeps the unsaved draft and the last valid constraints.
  const before=JSON.stringify(stored);get('exclusionAdd').onclick();points.forEach(click);failure=true;
  await get('exclusionFinish').onclick();assert.equal(JSON.stringify(stored),before);
  assert.equal(editor.ready(),false);assert.equal(get('exclusionStatus').textContent,'invalid polygon');failure=false;
  get('exclusionCancel').onclick();get('exclusionClose').onclick();
  assert.equal(click([0,0],{ctrlKey:true}).stopped,undefined);
  // Previews and pixel-only backgrounds cannot receive world-space drawing.
  state.preview={};editor.sync();assert.equal(get('exclusionToggle').disabled,true);state.preview=null;
  get('backgroundChoice').value='original';editor.sync();assert.equal(get('exclusionToggle').disabled,true);
  get('backgroundChoice').value='map';state.busy=true;editor.sync();assert.equal(get('exclusionToggle').disabled,true);state.busy=false;
  // Reloading a matching map uses the saved polygons; stale windows recover explicitly.
  editor.load({...state.track,exclusions:stored});assert.equal(editor.revision(),stored.revision);
  get('exclusionToggle').onclick();stored={...stored,revision:'999',zones:[]};await get('exclusionDelete').onclick();
  assert.equal(editor.revision(),'999');assert.equal(get('exclusionStatus').textContent,'conflict');
  await tick();console.log('Exclusion drawing, transform, undo, failed save, stale windows, and input isolation: OK');
})().catch(error=>{console.error(error);process.exitCode=1;});
