(() => {
  const points=document.querySelector('.waypoint-panel'),speed=document.querySelector('.velocity-controls');
  window.editMode='point';let box=null;
  function mode(value){box=null;window.editMode=value;points.hidden=value!=='point';speed.hidden=value!=='speed';points.open=speed.open=true;$('pointMode').setAttribute('aria-selected',String(value==='point'));$('speedMode').setAttribute('aria-selected',String(value==='speed'));draw();}
  $('pointMode').onclick=()=>mode('point');$('speedMode').onclick=()=>mode('speed');$('toVelocity').onclick=()=>mode('speed');
  const entry=()=>window.speedSystem.selectionEntry();
  $('speedSelectAll').onclick=()=>{const c=entry();if(c){c.selection=new Set(c.points.map((_,i)=>i));draw();}};
  $('speedClear').onclick=()=>{entry()?.selection.clear();draw();};
  function allowed(){return window.editMode==='speed'&&$('backgroundChoice')?.value!=='original'&&!window.waypointEditor?.locked;}
  const canvas=$('trackCanvas'),local=e=>{const r=canvas.getBoundingClientRect();return[e.clientX-r.left,e.clientY-r.top];};
  canvas.addEventListener('pointerdown',e=>{
    if(!allowed()||!e.ctrlKey||!$('showRoute').checked)return;const c=entry();if(!c?.screen)return;
    e.preventDefault();e.stopImmediatePropagation();const q=local(e);let index=-1,best=12;
    c.points.forEach((p,i)=>{const v=c.screen(p),d=Math.hypot(v[0]-q[0],v[1]-q[1]);if(d<best){best=d;index=i;}});
    if(index>=0){c.selection.has(index)?c.selection.delete(index):c.selection.add(index);draw();}
    else{box={c,start:q,end:q};canvas.setPointerCapture(e.pointerId);}
  },true);
  canvas.addEventListener('pointermove',e=>{if(!box)return;e.stopImmediatePropagation();box.end=local(e);draw();const [ctx]=canvasContext('trackCanvas');ctx.strokeStyle='#8ac9ff';ctx.fillStyle='#8ac9ff22';const {start:a,end:b}=box;ctx.fillRect(a[0],a[1],b[0]-a[0],b[1]-a[1]);ctx.strokeRect(a[0],a[1],b[0]-a[0],b[1]-a[1]);},true);
  canvas.addEventListener('pointerup',e=>{if(!box)return;e.stopImmediatePropagation();const {c,start:a}=box,b=local(e);if(c===entry())c.points.forEach((p,i)=>{const q=c.screen(p);if(q[0]>=Math.min(a[0],b[0])&&q[0]<=Math.max(a[0],b[0])&&q[1]>=Math.min(a[1],b[1])&&q[1]<=Math.max(a[1],b[1]))c.selection.add(i);});box=null;draw();},true);
  for(const event of ['pointercancel','lostpointercapture'])canvas.addEventListener(event,()=>{box=null;draw();});
  canvas.addEventListener('contextmenu',e=>{if(allowed())e.preventDefault();});
  $('speedCanvas').addEventListener('pointerdown',e=>{if(!allowed()||!e.ctrlKey)return;const c=entry();if(!c?.data)return;e.preventDefault();const r=e.currentTarget.getBoundingClientRect(),s=(e.clientX-r.left-48)/(r.width-68)*c.data.length;const i=c.data.s.reduce((best,v,j)=>Math.abs(v-s)<Math.abs(c.data.s[best]-s)?j:best,0);c.selection.has(i)?c.selection.delete(i):c.selection.add(i);draw();});
  $('speedCanvas').addEventListener('contextmenu',e=>{if(allowed())e.preventDefault();});
  function clearCurrent(){
    if(window.waypointEditor?.locked)return;
    box=null;
    if(window.editMode==='speed')$('speedClear').click();
    else if(window.waypointEditor?.active)$('editClearSelection').click();
  }
  canvas.addEventListener('dblclick',e=>{
    if(e.ctrlKey||e.metaKey||e.altKey||e.shiftKey||e.button!==0||$('backgroundChoice')?.value==='original')return;
    const editor=window.waypointEditor,c=entry();
    const route=window.editMode==='speed'?c?.points:editor?.active?editor.scene.route.points:null;
    const screen=window.editMode==='speed'?c?.screen:editor?.view?.screen;
    if(!route||!screen)return;
    const q=local(e);
    // Keep double-clicks on a waypoint or route segment from clearing selection.
    if($('showRoute').checked)for(let i=0;i<route.length;i++){
      const a=screen(route[i]),b=screen(route[(i+1)%route.length]),dx=b[0]-a[0],dy=b[1]-a[1];
      const t=Math.max(0,Math.min(1,((q[0]-a[0])*dx+(q[1]-a[1])*dy)/(dx*dx+dy*dy||1)));
      if(Math.hypot(q[0]-a[0]-t*dx,q[1]-a[1]-t*dy)<12)return;
    }
    e.preventDefault();clearCurrent();
  });
  document.addEventListener('keydown',e=>{
    if(e.key!=='Escape'||e.ctrlKey||e.metaKey||e.altKey||e.shiftKey)return;
    const target=e.target;
    if(target?.closest?.('input,textarea,select,[contenteditable]:not([contenteditable="false"])'))return;
    e.preventDefault();clearCurrent();
  });
  const help='Ctrl 点击增减选点；Ctrl 拖动空白处框选。松开 Ctrl 后双击画布空白处，或按 Esc，清除当前选择。';
  canvas.title=help;
  for(const panel of [points,speed]){const hint=document.createElement('p');hint.className='hint selection-help';hint.textContent='取消选择：松开 Ctrl，双击画布空白处 / Esc';panel.prepend(hint);}
  mode('point');
})();
