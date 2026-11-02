/* World-coordinate planning exclusions. No input is intercepted when closed. */
(() => {
  const canvas=$('trackCanvas'),panel=$('exclusionPanel');
  let config=null,trackId=null,open=false,drawing=false,draft=[],cursor=null,pending=false;
  let selected=0,history=[],view=null;
  const copy=value=>JSON.parse(JSON.stringify(value));
  const tr=text=>window.i18n.t(text);
  function available(){return !!state.track&&!state.preview&&$('backgroundChoice').value!=='original'&&(!window.waypointEditor?.active||window.waypointEditor.source!=='preview');}
  function note(text,error=false){$('exclusionStatus').textContent=text;$('exclusionStatus').classList.toggle('error',error);}
  function sync(){
    const ready=available(),locked=state.busy||pending;
    if((!ready||state.busy)&&open){open=false;drawing=false;draft=[];cursor=null;}
    panel.hidden=!open;
    canvas.classList.toggle('drawing-exclusion',drawing);
    $('exclusionToggle').disabled=!ready||locked;
    $('exclusionToggle').setAttribute('aria-expanded',String(open));
    $('exclusionCount').textContent=config?.zones.length?' · '+config.zones.length:'';
    $('exclusionAdd').disabled=locked||drawing||!ready||(config?.zones.length||0)>=20;
    $('exclusionFinish').hidden=$('exclusionVertexUndo').hidden=$('exclusionCancel').hidden=!drawing;
    $('exclusionFinish').disabled=locked||draft.length<3;
    $('exclusionVertexUndo').disabled=locked||!draft.length;
    $('exclusionDelete').disabled=locked||drawing||!config?.zones.length;
    $('exclusionUndo').disabled=locked||drawing||!history.length;
    $('exclusionList').disabled=locked||drawing||!config?.zones.length;
    if(pending||drawing)$('optimize').disabled=true;
    else if(!state.busy)$('optimize').disabled=!state.track||!!state.preview;
  }
  function list(){
    const select=$('exclusionList');select.replaceChildren();
    (config?.zones||[]).forEach((zone,i)=>{const option=document.createElement('option');option.value=i;option.textContent=tr('区域')+' '+(i+1);select.append(option);});
    selected=Math.max(0,Math.min(selected,(config?.zones.length||1)-1));select.value=selected;
  }
  function load(track){
    trackId=track.id;config=copy(track.exclusions||{zones:[],revision:null});
    open=drawing=false;draft=[];cursor=null;history=[];selected=0;view=null;list();sync();
  }
  function changed(){
    state.track.exclusions=copy(config);
    if(state.result){
      state.result.exclusion_stale=true;
      $('resultState').textContent='禁行区已改变 · 请重新计算';
      $('resultState').className='result-state';
      $('checks').textContent='上次结果对应旧禁行区，请重新计算以检查新范围。';
    }
    $('stageBadge').textContent='禁行区已改变 · 请重新计算';$('stageBadge').className='badge';
    say('禁行区已保存。点击原来的计算按钮，按剩余范围重新优化。');
  }
  async function save(zones,remember=true){
    if(pending||state.busy||!trackId)return false;
    const id=trackId,previous=copy(config.zones);pending=true;sync();note('正在保存禁行区…');
    try{
      const response=await fetch('/api/tracks/'+id+'/exclusions',{method:'POST',headers:{'Content-Type':'application/json','X-Raceline-Local':'1'},body:JSON.stringify({zones,revision:config.revision})});
      const data=await response.json();
      if(id!==trackId)return false;
      if(!response.ok){
        if(response.status===409&&data.current){config=data.current;history=[];state.track.exclusions=copy(config);list();changed();}
        throw Error(data.error||'禁行区保存失败，请重试。');
      }
      config=data;if(remember){history.push(previous);if(history.length>30)history.shift();}
      state.track.exclusions=copy(config);list();changed();note('已保存；下次计算生效。');return true;
    }catch(error){if(id===trackId)note(error.message,true);return false;}
    finally{pending=false;sync();draw();}
  }
  function cancel(){drawing=false;draft=[];cursor=null;sync();draw();note('已取消本次绘制。');}
  function add(){
    if(!available()||state.busy||pending||config.zones.length>=20)return;
    drawing=true;draft=[];cursor=null;
    note('依次点击顶点，点击起点或按 Enter 完成；Esc 取消。');sync();draw();
  }
  async function finish(){
    if(!drawing||draft.length<3||pending)return;
    const polygon=copy(draft);
    if(await save([...config.zones,polygon])){selected=config.zones.length-1;drawing=false;draft=[];cursor=null;list();sync();draw();}
  }
  function local(event){const r=canvas.getBoundingClientRect();return[event.clientX-r.left,event.clientY-r.top];}
  function world(q){return[view.cx+(q[0]-view.x)/view.s,view.cy-(q[1]-view.y)/view.s];}
  function contains(q,polygon){let inside=false;for(let i=0,j=polygon.length-1;i<polygon.length;j=i++){
    const a=polygon[i],b=polygon[j];if((a[1]>q[1])!==(b[1]>q[1])&&q[0]<(b[0]-a[0])*(q[1]-a[1])/(b[1]-a[1])+a[0])inside=!inside;
  }return inside;}
  function paint(ctx,screen,transform){
    if(!available()||!config)return;
    if(transform)view=transform;
    for(let i=0;i<config.zones.length;i++){
      const zone=config.zones[i];ctx.beginPath();zone.forEach((p,j)=>{const q=screen(p);j?ctx.lineTo(...q):ctx.moveTo(...q);});ctx.closePath();
      ctx.fillStyle='#ef617538';ctx.fill();ctx.strokeStyle=open&&i===selected?'#ffb1bb':'#ee6d7f';ctx.lineWidth=open&&i===selected?2:1.2;ctx.stroke();
      const q=screen(zone[0]);ctx.fillStyle='#ffabb7';ctx.font='11px system-ui';ctx.fillText(tr('禁行区')+' '+(i+1),q[0]+5,q[1]-6);
    }
    if(drawing&&draft.length){
      ctx.beginPath();draft.forEach((p,i)=>{const q=screen(p);i?ctx.lineTo(...q):ctx.moveTo(...q);});if(cursor)ctx.lineTo(...screen(cursor));
      ctx.setLineDash([5,4]);ctx.strokeStyle='#ffb1bb';ctx.lineWidth=1.5;ctx.stroke();ctx.setLineDash([]);
      for(let i=0;i<draft.length;i++){ctx.beginPath();ctx.arc(...screen(draft[i]),i===0?6:3.5,0,2*Math.PI);ctx.fillStyle='#ffb1bb';ctx.fill();}
    }
  }
  $('exclusionToggle').onclick=()=>{open=!open;drawing=false;draft=[];cursor=null;list();note('圈出不希望车辆进入的区域，不修改原地图。');sync();draw();};
  $('exclusionClose').onclick=()=>{open=false;cancel();};
  $('exclusionAdd').onclick=add;$('exclusionFinish').onclick=finish;$('exclusionCancel').onclick=cancel;
  $('exclusionVertexUndo').onclick=()=>{draft.pop();sync();draw();};
  $('exclusionList').onchange=()=>{selected=Number($('exclusionList').value);draw();};
  $('exclusionDelete').onclick=()=>save(config.zones.filter((_,i)=>i!==selected));
  $('exclusionUndo').onclick=async()=>{const old=history.at(-1);if(old&&await save(old,false)){history.pop();sync();}};
  canvas.addEventListener('pointerdown',event=>{
    if(!open||!available()||state.busy||pending||event.button!==0||!view)return;
    if(drawing){
      event.preventDefault();event.stopImmediatePropagation();const q=local(event);
      if(draft.length>=3&&Math.hypot(...q.map((v,i)=>v-view.screen(draft[0])[i]))<10){finish();return;}
      if(draft.length>=64){note('每个禁行区最多 64 个顶点，请完成当前区域。',true);return;}
      const p=world(q);if(!draft.length||Math.hypot(p[0]-draft.at(-1)[0],p[1]-draft.at(-1)[1])>1e-6)draft.push(p);
      cursor=p;sync();draw();return;
    }
    if(event.ctrlKey||event.metaKey)return;
    const p=world(local(event));const index=config.zones.findLastIndex(zone=>contains(p,zone));
    if(index>=0){event.preventDefault();event.stopImmediatePropagation();selected=index;list();draw();}
  },true);
  for(const type of ['pointermove','pointerup','pointercancel','dblclick'])canvas.addEventListener(type,event=>{
    if(!drawing||!available())return;event.stopImmediatePropagation();
    if(type==='pointermove'&&view){cursor=world(local(event));draw();}
  },true);
  document.addEventListener('keydown',event=>{
    if(!open||event.target?.closest?.('input,textarea,select,[contenteditable="true"]'))return;
    if(event.key==='Escape'){event.preventDefault();event.stopImmediatePropagation();if(drawing)cancel();else{open=false;sync();draw();}}
    else if(drawing&&event.key==='Enter'){event.preventDefault();event.stopImmediatePropagation();finish();}
    else if(drawing&&event.key==='Backspace'){event.preventDefault();event.stopImmediatePropagation();draft.pop();sync();draw();}
  },true);
  window.addEventListener('raceline-language-change',()=>{list();draw();});
  window.exclusionEditor={load,sync,paint,revision:()=>config?.revision,ready:()=>!pending&&!drawing};
  sync();
})();
