(() => {
  let focus='points',lastObject=null;
  function currentName(){const e=window.waypointEditor;if(e?.active)return e.displayName||e.source;return state.preview?.route?.path||state.track?.name||'未打开路线';}
  function update(){
    const v=window.speedSystem?.status()||{},e=window.waypointEditor,has=!!v.count;const object=e?.active?e.scene:state.preview||state.result||state.track;if(object!==lastObject){lastObject=object;focus='points';}
    const phase=!has?'打开文件':state.busy?'选择路线':focus==='save'?'检查与保存':focus==='speed'?'设置速度':e?.active?'编辑点位':'选择路线';
    const names=['打开文件','选择路线','编辑点位','设置速度','检查与保存'];
    $('workflowSteps').replaceChildren(...names.map((name,i)=>{const span=document.createElement('span');span.textContent=`${i+1} ${name}`;span.className=name===phase?'current':'';if(name===phase)span.setAttribute('aria-current','step');return span;}));
    const speed=v.ready?(v.manual?'速度已更新 · 手动调整':'速度已更新'):v.pending?'速度重算中':'速度未就绪';
    $('workflowContext').textContent=has?`${currentName()} · ${v.label} · ${v.count} 点 · ${speed}`:'从左栏连接 Jetson 并打开地图 / CSV；已有路线可跳过规划，直接编辑。';
    $('workflowSteps').title=$('workflowContext').textContent;
    const key=$('remoteSource').value;let source,count,format,ready=true;
    if(['speed','pp','mppi'].includes(key)){source=currentName()+' · '+(v.label||'无路线');count=v.count;format={speed:'通用 CSV · m/s',pp:'Pure Pursuit · 0–1 比例＋μ',mppi:'MPPI · m/s＋μ'}[key];ready=v.ready;}
    else if(key==='edited'){source=e?.source?(e.displayName||e.source)+' · 编辑副本':'尚无编辑副本';count=e?.scene?.route?.points?.length||0;format='几何 CSV · 不含速度';ready=!!state.editedFiles;}
    else {source=(state.track?.name||'无路线')+(key==='center'?' · 原中心线':' · 原优化结果');count=key==='center'?state.track?.center?.length:state.result?.route?.length;format='几何 CSV · 不含速度';ready=key==='center'?!!state.track?.files:!!state.result?.files;}
    $('saveSummary').textContent=`保存对象：${source}\n点数：${count||'—'}\n格式：${format}\n${['speed','pp','mppi'].includes(key)?speed:ready?'文件已生成':'请先生成 / 导出对应文件'}${(key==='edited'||(['speed','pp','mppi'].includes(key)&&e?.active))?'\n几何编辑尚未重新验证边界与曲率。':''}`;
    $('saveSummary').classList.toggle('not-ready',!ready);
  }
  document.querySelector('.waypoint-panel').addEventListener('focusin',()=>{focus='points';update();});
  document.querySelector('.velocity-controls').addEventListener('focusin',()=>{focus='speed';update();});
  document.querySelector('.remote-save').addEventListener('focusin',()=>{focus='save';update();});
  $('remoteSource').addEventListener('change',update);
  new MutationObserver(update).observe($('editMessage'),{childList:true,subtree:true,characterData:true});
  $('toVelocity').onclick=()=>{focus='speed';const panel=document.querySelector('.velocity-controls');panel.open=true;panel.scrollIntoView({block:'start',behavior:'smooth'});update();};
  $('toSave').onclick=()=>{focus='save';const panel=document.querySelector('.remote-save').parentElement;panel.open=true;panel.scrollIntoView({block:'nearest',behavior:'smooth'});update();};
  window.workflow={update};update();
})();
