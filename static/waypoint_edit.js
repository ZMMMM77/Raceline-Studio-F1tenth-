(() => {
  const editor={active:false,scene:null,selected:-1,selection:new Set(),boxMode:false,box:null,history:[],future:[],view:null,locked:false,version:0,dirty:false,source:''};
  const canvas=$('trackCanvas');let moving=null;
  const copy=points=>points.map(p=>p.slice());
  const note=(text,error=false)=>{$('editMessage').textContent=text;$('editMessage').classList.toggle('error',error);};
  function sync(){
    $('editControls').hidden=!editor.active;$('editResume').hidden=editor.active||!editor.scene;
    const p=editor.scene?.route.points;
    $('editUndo').disabled=editor.locked||!editor.history.length;$('editRedo').disabled=editor.locked||!editor.future.length;
    for(const id of ['editCount','editCornerBias','editResample','editExport','editCoordinate','editSmoothAll','editSmoothSelection','editBox','editSelectAll','editClearSelection'])$(id).disabled=editor.locked;
    $('editX').disabled=$('editY').disabled=editor.selected<0||editor.locked;
    if(editor.selected>=0&&p){$('editX').value=p[editor.selected][0].toFixed(6);$('editY').value=p[editor.selected][1].toFixed(6);$('editSelected').textContent=`已选 ${editor.selection.size} 点 · 当前 ${editor.selected+1} / ${p.length}`;}else{$('editX').value=$('editY').value='';$('editSelected').textContent='按住 Ctrl 点击选点或取消；Ctrl 拖动空白处框选。';}
    if(editor.active){$('stageBadge').textContent='Waypoint 编辑 · 待验证';$('stageBadge').className='badge';$('plotInfo').textContent=`${p.length} 个 waypoints · 闭环编辑副本 · 未重新验证`;}
  }
  function remember(){editor.history.push(copy(editor.scene.route.points));if(editor.history.length>40)editor.history.shift();editor.future=[];}
  function changed(){editor.dirty=true;editor.version++;state.editedFiles=null;sync();draw();}
  async function begin(){
    if(state.busy||editor.locked){note('请等待当前计算或保存完成。',true);return;}
    const source=$('editSource').value;let route,map=null;
    if(source==='preview'){route=state.preview?.route?.points;map=state.preview?.map;}else{route=source==='result'?state.result?.route:state.track?.center;if(state.track?.map&&state.image)map={...state.track.map,image:state.image};}
    if(!route||route.length<12){note('请先生成所选路线，或打开至少 12 个点的 CSV。',true);return;}
    let p=copy(route);if(Math.hypot(p[0][0]-p.at(-1)[0],p[0][1]-p.at(-1)[1])<1e-7)p.pop();
    if(p.length>5000){note('当前路线超过 5000 点，请先减小输入文件或调整生成间距。',true);return;}
    if(editor.dirty&&!confirm('重新从所选原路线开始？当前未导出的编辑副本会被替换。'))return;
    let boundaries=null;
    if(source==='preview')boundaries=state.preview?.route?.boundaries||null;
    else if(state.track?.widths&&state.track.boundary_mode!=='map'){
      const c=state.track.center,widths=state.track.widths,right=[],left=[];
      for(let i=0;i<c.length;i++){const a=c[(i+c.length-1)%c.length],b=c[(i+1)%c.length],dx=b[0]-a[0],dy=b[1]-a[1],len=Math.max(Math.hypot(dx,dy),1e-10);right.push([c[i][0]+dy/len*widths[i][0],c[i][1]-dx/len*widths[i][0]]);left.push([c[i][0]-dy/len*widths[i][1],c[i][1]+dx/len*widths[i][1]]);}boundaries=[right,left];
    }
    if(source!=='preview'&&state.track?.map&&!map){
      const meta=state.track.map,img=new Image();try{await new Promise((resolve,reject)=>{img.onload=resolve;img.onerror=reject;img.src=meta.url;});map={...meta,image:img};}catch{note('地图尚未加载成功，请稍后再进入编辑。',true);return;}
    }
    editor.scene={map,boundaries,editing:true,route:{points:p,count:p.length,closed:true},bounds:null};editor.source=source==='preview'?state.preview.path:source==='result'?'优化轨迹 '+state.result.result_id:'中心线 '+state.track.id;
    window.speedSystem?.inherit(source==='preview'?state.preview.route:source==='result'?state.result:state.track,editor.scene.route);
    editor.displayName=source==='preview'?state.preview.path:state.track.name;editor.active=true;editor.selected=-1;editor.selection.clear();editor.history=[];editor.future=[];editor.dirty=false;editor.version++;state.editedFiles=null;
    $('editCount').value=p.length;$('editCornerBias').value='0';$('editCornerBiasValue').textContent='0% · 等距';$('emptyState').hidden=true;document.body.classList.add('waypoint-edit-mode');state.scale=1;state.pan=[0,0];sync();draw();note('已打开编辑副本。Ctrl 点击选点，松开 Ctrl 后拖动选中点。');
  }
  editor.close=()=>{
    if(!editor.active)return;moving=null;editor.box=null;editor.active=false;editor.version++;document.body.classList.remove('waypoint-edit-mode');$('editControls').hidden=true;
    if(state.preview){updatePreviewInfo();$('stageBadge').textContent='文件预览';}else if(state.track){$('stageBadge').textContent='原规划路线';$('plotInfo').textContent=`${state.track.center.length} 个参考点 · 米制坐标`;}
    sync();draw();
  };
  editor.draw=(ctx,w,h)=>{
    editor.view=drawFilePreview(ctx,w,h,editor.scene);
    if(!editor.scene.bounds)editor.scene.bounds=editor.view.bounds;
    if(window.editMode==='speed'||!$('showRoute').checked)return;
    const p=editor.scene.route.points;
    ctx.fillStyle='#4bd9bc';ctx.strokeStyle='#12273a';ctx.lineWidth=1;
    for(let i=0;i<p.length;i++){ctx.beginPath();ctx.arc(...editor.view.screen(p[i]),(window.editMode!=='speed'&&editor.selection.has(i))?5:3,0,Math.PI*2);ctx.fillStyle=(window.editMode!=='speed'&&editor.selection.has(i))?'#ffffff':(window.speedSystem?.pointColor(i)||'#4bd9bc');ctx.fill();ctx.stroke();}
    if(editor.box){const {start,end}=editor.box;ctx.fillStyle='#60a5fa24';ctx.strokeStyle='#79b7ff';ctx.setLineDash([5,4]);ctx.fillRect(start[0],start[1],end[0]-start[0],end[1]-start[1]);ctx.strokeRect(start[0],start[1],end[0]-start[0],end[1]-start[1]);ctx.setLineDash([]);}
  };
  window.waypointEditor=editor;
  const old={down:canvas.onpointerdown,move:canvas.onpointermove,up:canvas.onpointerup,cancel:canvas.onpointercancel};
  const local=e=>{const r=canvas.getBoundingClientRect();return[e.clientX-r.left,e.clientY-r.top];};
  function nearest(e){const q=local(e);let best=-1,distance=12;editor.scene.route.points.forEach((p,i)=>{const screen=editor.view.screen(p),d=Math.hypot(q[0]-screen[0],q[1]-screen[1]);if(d<distance){best=i;distance=d;}});return best;}
  canvas.onpointerdown=e=>{
    if(editor.active&&editor.locked)return;
    if(window.editMode!=='speed'&&editor.active&&$('showRoute').checked&&(e.button===0||(e.ctrlKey&&e.button===2))){
      const i=nearest(e);
      if(i>=0){
        if(e.ctrlKey){e.preventDefault();if(editor.selection.has(i))editor.selection.delete(i);else editor.selection.add(i);editor.selected=editor.selection.has(i)?i:[...editor.selection][0]??-1;sync();draw();return;}
        if(!editor.selection.has(i)||!$('editDrag').checked){old.down?.(e);return;}editor.selected=i;
        moving={snapshot:copy(editor.scene.route.points),indices:[...editor.selection],start:local(e),scale:editor.view.scale,changed:false};canvas.setPointerCapture(e.pointerId);sync();draw();return;
      }
      if(e.ctrlKey){e.preventDefault();editor.box={start:local(e),end:local(e),initial:new Set(editor.selection)};canvas.setPointerCapture(e.pointerId);draw();return;}
    }
    old.down?.(e);
  };
  // macOS Control-click may be delivered as a secondary click.
  canvas.addEventListener('contextmenu',e=>{if(editor.active)e.preventDefault();});
  canvas.onpointermove=e=>{
    if(editor.box){editor.box.end=local(e);draw();return;}
    if(moving&&editor.active){const q=local(e),dx=(q[0]-moving.start[0])/moving.scale,dy=-(q[1]-moving.start[1])/moving.scale;if(Math.hypot(q[0]-moving.start[0],q[1]-moving.start[1])<2&&!moving.changed)return;for(const i of moving.indices)editor.scene.route.points[i]=[moving.snapshot[i][0]+dx,moving.snapshot[i][1]+dy];moving.changed=true;sync();draw();return;}old.move?.(e);
  };
  canvas.onpointerup=e=>{
    if(editor.box){const box=editor.box;editor.selection=box.initial;const xmin=Math.min(box.start[0],box.end[0]),xmax=Math.max(box.start[0],box.end[0]),ymin=Math.min(box.start[1],box.end[1]),ymax=Math.max(box.start[1],box.end[1]);editor.scene.route.points.forEach((p,i)=>{const [x,y]=editor.view.screen(p);if(x>=xmin&&x<=xmax&&y>=ymin&&y<=ymax)editor.selection.add(i);});editor.selected=[...editor.selection][0]??-1;editor.box=null;sync();draw();note(`已选中 ${editor.selection.size} 个点。拖动其中一个点可整体移动。`);return;}
    if(moving){if(moving.changed){editor.history.push(moving.snapshot);if(editor.history.length>40)editor.history.shift();editor.future=[];changed();note(`已移动 ${moving.indices.length} 个节点，可撤销。`);}moving=null;return;}old.up?.(e);
  };
  function cancelMove(){if(moving){editor.scene.route.points=moving.snapshot;moving=null;}editor.box=null;sync();draw();}
  canvas.onpointercancel=e=>{cancelMove();old.cancel?.(e);};
  canvas.addEventListener('lostpointercapture',()=>{if(moving||editor.box)cancelMove();});
  $('editBoundary').onchange=draw;
  $('editBox').onclick=()=>{editor.boxMode=!editor.boxMode;$('editBox').setAttribute('aria-pressed',String(editor.boxMode));note(editor.boxMode?'在空白处拖出矩形框选节点；拖动选中点可整体移动。':'已恢复空白处拖动平移。');};
  $('editSelectAll').onclick=()=>{editor.selection=new Set(editor.scene.route.points.map((_,i)=>i));editor.selected=0;sync();draw();};
  $('editClearSelection').onclick=()=>{editor.selection.clear();editor.selected=-1;sync();draw();};
  $('editResume').onclick=()=>{if(!editor.scene||state.busy||editor.locked)return;editor.active=true;editor.version++;document.body.classList.add('waypoint-edit-mode');$('emptyState').hidden=true;state.scale=1;state.pan=[0,0];sync();draw();note('已恢复上次编辑副本。');};
  $('editBegin').onclick=begin;$('editExit').onclick=editor.close;
  $('editCoordinate').onclick=()=>{if(editor.locked||editor.selected<0)return;const x=$('editX').value,y=$('editY').value;if(!x.trim()||!y.trim()||!Number.isFinite(+x)||!Number.isFinite(+y)){note('请输入有效的 X/Y 坐标。',true);return;}remember();const p=editor.scene.route.points,dx=+x-p[editor.selected][0],dy=+y-p[editor.selected][1];for(const i of editor.selection)p[i]=[p[i][0]+dx,p[i][1]+dy];changed();note('已按当前节点坐标移动所选节点。');};
  $('editUndo').onclick=()=>{if(editor.locked||!editor.history.length)return;editor.future.push(copy(editor.scene.route.points));editor.scene.route.points=editor.history.pop();editor.selected=-1;editor.selection.clear();$('editCount').value=editor.scene.route.points.length;changed();$('editCornerBias').oninput();note('已撤销。');};
  $('editRedo').onclick=()=>{if(editor.locked||!editor.future.length)return;editor.history.push(copy(editor.scene.route.points));editor.scene.route.points=editor.future.pop();editor.selected=-1;editor.selection.clear();$('editCount').value=editor.scene.route.points.length;changed();$('editCornerBias').oninput();note('已重做。');};
  $('editCornerBias').oninput=()=>{const value=Number($('editCornerBias').value);$('editCornerBiasValue').textContent=value?`${value}% · 待应用`:'0% · 等距（待应用）';};
  $('editResample').onclick=async()=>{if(editor.locked)return;const count=Number($('editCount').value),cornerBias=Number($('editCornerBias').value)/100;if(!Number.isInteger(count)||count<12||count>5000){note('请输入 12–5000 的整数点数。',true);return;}editor.locked=true;sync();const version=editor.version;try{const d=await api('/api/waypoints/resample',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({points:editor.scene.route.points,count,corner_bias:cornerBias})});if(editor.version!==version)return;remember();editor.scene.route.points=d.points;editor.selected=-1;editor.selection.clear();changed();$('editCornerBiasValue').textContent=cornerBias?`${Math.round(cornerBias*100)}% · 已应用`:'0% · 等距';note(`已生成 ${d.count} 个 waypoint · ${cornerBias?'弯道加密 '+Math.round(cornerBias*100)+'%':'等距分布'}，保留起点，可撤销。`);}catch(e){note(e.message,true);}finally{editor.locked=false;sync();}};
  async function smooth(all){
    if(editor.locked)return;const selection=all?null:[...editor.selection];if(selection&&selection.length<3){note('请至少选中三个节点，或使用“平滑整圈”。',true);return;}
    editor.locked=true;sync();const version=editor.version;
    try{const d=await api('/api/waypoints/smooth',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({points:editor.scene.route.points,selection,iterations:Number($('editSmoothLevel').value),strength:.6})});if(editor.version!==version)return;remember();editor.scene.route.points=d.points;changed();note(all?'整圈已平滑，点数不变，可撤销。':'所选节点已平滑，未选节点保持不变，可撤销。');}catch(e){note(e.message,true);}finally{editor.locked=false;sync();}
  }
  $('editSmoothSelection').onclick=()=>smooth(false);$('editSmoothAll').onclick=()=>smooth(true);
  $('editExport').onclick=async()=>{if(editor.locked)return;editor.locked=true;sync();const version=editor.version;try{const d=await api('/api/waypoints/export',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({points:editor.scene.route.points,source:editor.source})});if(editor.version!==version)return;state.editedFiles=d.files;editor.dirty=false;const a=document.createElement('a');a.href=d.files.edited+'?download=1';a.download='edited_waypoints.csv';a.click();note(`已导出 ${d.count} 个点。${d.report.self_crossing?'注意：路径存在自交。':''}可在“保存到 Jetson”选择编辑后的 CSV。`);}catch(e){note(e.message,true);}finally{editor.locked=false;sync();}};
  const fit=$('fit').onclick;$('fit').onclick=()=>{if(editor.active)editor.scene.bounds=null;fit();};
  for(const id of ['clearPreviewMap','backToPlanning']){const previous=$(id).onclick;$(id).onclick=()=>{editor.close();previous?.();};}
  sync();
})();
