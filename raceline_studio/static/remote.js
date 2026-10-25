(() => {
  let working=false,connected=false,lastPath=null,remoteRoots=[],identity=null;
  function message(text,error=false){$('remoteMessage').textContent=text;$('remoteMessage').classList.toggle('error',error);}
  async function requestJSON(prefix,action,body){const r=await fetch(prefix+action,{method:body===undefined?'GET':'POST',headers:{'X-Raceline-Local':'1','Content-Type':'application/json'},...(body===undefined?{}:{body:JSON.stringify(body)})});const d=await r.json();if(!r.ok){const e=Error(d.error||'请求失败');e.data=d;throw e;}return d;}
  const ssh=(action,body)=>requestJSON('/api/remote/',action,body);
  const files=ssh;
  async function run(fn){if(working)return;working=true;const buttons=[...document.querySelectorAll('.connection-settings button,.remote-path button,.explorer-toolbar button,#remoteSave')],disabled=buttons.map(b=>b.disabled);buttons.forEach(b=>b.disabled=true);try{await fn();}catch(e){message(e.message,true);}finally{working=false;buttons.forEach((b,i)=>b.disabled=disabled[i]);syncPlanning();}}
  function resetPreview(){window.waypointEditor?.close();state.preview=null;lastPath=null;document.body.classList.remove('file-preview-mode');$('fileInfo').textContent='从左侧打开地图或路线。';$('clearPreviewMap').hidden=true;$('backToPlanning').hidden=true;$('emptyState').hidden=!!state.track;$('trackName').textContent=state.track?.name||'打开地图或路线';$('stageBadge').textContent=state.track?'规划工作区':'等待打开';draw();}
  function status(d){connected=d.connected;remoteRoots=d.directories||[];$('remoteStatus').textContent=connected?`${d.identity.username}@${d.identity.host}`:'未连接 · 设置 SSH';$('remoteDot').classList.toggle('connected',connected);if(connected)document.querySelector('.connection-settings').open=false;const next=JSON.stringify(d.identity);if(connected&&identity&&identity!==next)resetPreview();if(connected)identity=next;window.remotePlanning?.sync();}
  function settings(){return{host:$('sshHost').value.trim(),username:$('sshUser').value.trim(),port:Number($('sshPort').value),password:$('sshPassword').value,auto_connect:$('sshAuto').checked,directory:remoteRoots[0]?.path||'~'};}
  async function connect(){message('正在连接 Jetson…');const d=settings();let result;try{result=await ssh('connect',d);}catch(e){if(!e.data?.fingerprint)throw e;if(!window.i18n.confirm(`首次连接 ${d.host}，请核对主机指纹：\n${e.data.fingerprint}\n\n信任此主机？`)){message('已取消连接。');return;}result=await ssh('connect',{...d,fingerprint:e.data.fingerprint});}finally{$('sshPassword').value='';}status(result);await buildTree();}
  async function open(path){if(state.busy)throw Error('请等待当前计算完成。');message('正在打开 '+path.split('/').pop()+'…');const d=await files('preview',{path,format:$('previewFormat').value});d.remote_identity=identity;d.csv_format=$('previewFormat').value;await openFilePreview(d);lastPath=path;if(d.kind==='route')$('remoteTarget').value=path;document.querySelectorAll('.remote-entry').forEach(b=>b.classList.toggle('selected',b.dataset.path===path));message(d.note);}
  let treeId=0;
  function treeIcon(kind){
    const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');
    svg.setAttribute('viewBox','0 0 20 20');svg.setAttribute('aria-hidden','true');
    svg.classList.add('tree-icon',`tree-icon-${kind}`);
    const path=document.createElementNS(svg.namespaceURI,'path');
    path.setAttribute('d',kind==='folder'?'M2.5 5.5h6l1.5 2h7.5v9h-15z M2.5 7.5v-4h5l2 2h8v2':kind==='image'?'M4 2.5h8l4 4v11H4z M12 2.5v4h4 M5.5 14l3-3 2.5 2 2-2 2 3 M7 7.5h.01':kind==='config'?'M4 2.5h8l4 4v11H4z M12 2.5v4h4 M7 10h6 M7 13h6':'M4 2.5h8l4 4v11H4z M12 2.5v4h4 M7 10h6 M7 13h6 M9.5 9v6');
    svg.append(path);return svg;
  }
  function branch(name,path,isDirectory,depth=0){
    const item=document.createElement('div'),b=document.createElement('button');
    item.className='tree-node';item.style.setProperty('--tree-depth',depth);
    b.className='remote-entry';b.type='button';b.dataset.path=path;b.title=path;
    b.classList.toggle('selected',path===lastPath);b.id=`remote-tree-${++treeId}`;
    const guides=document.createElement('span');guides.className='tree-guides';guides.setAttribute('aria-hidden','true');
    for(let i=0;i<depth;i++)guides.append(document.createElement('i'));
    const arrow=document.createElement('span');arrow.className='tree-chevron';arrow.setAttribute('aria-hidden','true');
    arrow.textContent=isDirectory?'›':'';
    const kind=isDirectory?'folder':/\.(csv|txt)$/i.test(name)?'table':/\.ya?ml$/i.test(name)?'config':'image';
    const label=document.createElement('span');label.className='file-name';label.textContent=name;
    b.append(guides,arrow,treeIcon(kind),label);item.append(b);
    item.classList.toggle('tree-root',depth===0);
    if(isDirectory){
      item.classList.add('tree-directory');
      const children=document.createElement('div');children.className='tree-children';children.hidden=true;
      children.id=`${b.id}-children`;children.setAttribute('role','group');children.setAttribute('aria-labelledby',b.id);
      item.append(children);b.setAttribute('aria-controls',children.id);b.setAttribute('aria-expanded','false');let loaded=false;
      async function toggle(){
        if(!children.hidden){children.hidden=true;b.setAttribute('aria-expanded','false');return;}
        if(!loaded){
          b.setAttribute('aria-busy','true');
          try{
            const d=await files('list',{path});
            const entries=d.entries.filter(e=>e.directory||/\.(csv|txt|yaml|yml|png|pgm|jpg|jpeg)$/i.test(e.name));
            entries.sort((a,b)=>Number(b.directory)-Number(a.directory)||a.name.localeCompare(b.name,undefined,{numeric:true,sensitivity:'base'}));
            for(const e of entries)children.append(branch(e.name,e.path||d.path.replace(/\/$/,'')+'/'+e.name,e.directory,depth+1).item);
            if(!children.childElementCount){const empty=document.createElement('p');empty.className='tree-empty';empty.style.setProperty('--tree-depth',depth+1);empty.textContent='没有地图或路线文件';children.append(empty);}
            loaded=true;
          }finally{b.removeAttribute('aria-busy');}
        }
        children.hidden=false;b.setAttribute('aria-expanded','true');
      }
      b.onclick=()=>run(toggle);return{item,expand:toggle};
    }
    b.onclick=()=>run(()=>open(path));return{item};
  }
  async function buildTree(override){$('remoteListing').replaceChildren();$('remoteRoots').replaceChildren();if(!connected){$('remoteListing').textContent='连接 Jetson 后显示文件树。';return;}
    const roots=override?[{label:override.split('/').pop()||'Jetson',path:override}]:remoteRoots;
    $('remoteDirectory').value=roots[0]?.path||'~';$('fileCount').textContent='展开文件夹 · 单击预览';
    const errors=[];
    for(const r of roots){const node=branch(r.label,r.path,true);$('remoteListing').append(node.item);try{await node.expand();}catch(e){errors.push(r.label+'：'+e.message);}}
    message(errors.length?errors.join('\n'):'单击文件预览；展开文件夹浏览下一级。',!!errors.length);
  }
  function syncPlanning(){
    const route=state.preview?.route,box=$('remotePlanningSource');
    box.hidden=!route;
    if(route){
      $('remotePlanningPath').textContent=route.path;
      $('remotePlanningPath').title=route.path;
      $('remotePlanningMap').textContent=state.preview.map?.yaml_path?'附带当前远程地图与 YAML。':state.preview.map?'当前背景图缺少 YAML，仅作参考。':'未附地图：使用 CSV 宽度，或在高级导入设置填写单侧宽度。';
    }
    $('importRemote').disabled=!connected||!route||state.busy||working;
    $('optimize').disabled=state.busy||!state.track||!!state.preview;
  }
  window.remotePlanning={sync:syncPlanning};
  $('importRemote').onclick=()=>run(async()=>{
    const route=state.preview?.route,map=state.preview?.map;
    if(!route)throw Error('请先从文件树打开远程 CSV。');
    if(state.busy)return;
    if(route.remote_identity!==identity)throw Error('SSH 连接已改变，请重新打开远程 CSV 后导入。');
    busy(true,'正在导入…');message('正在将远程 CSV 导入规划…');
    try{
      const form=new FormData();
      for(const [key,value] of Object.entries({source:'remote',mode:'csv',remote_csv:route.path,remote_identity:identity,csv_format:route.csv_format||'auto',reverse:$('reverse').checked,fallback_width:$('fallbackWidth').value,boundary_source:$('boundarySource').value}))form.append(key,value);
      if(map?.yaml_path)form.append('remote_yaml',map.yaml_path);
      else if(map?.path)form.append('remote_image',map.image_path||map.path);
      const data=await api('/api/import',{method:'POST',body:form});
      await loadTrack(data);
      message('远程 CSV 已导入规划，可设置车辆约束并计算最小曲率行车线。');
      say(['远程 CSV 已导入规划，可设置车辆约束并计算最小曲率行车线。',...data.warnings].join('\n'));
      $('vehicleSettings').open=true;
    }catch(e){
      say(e.message,true);
      if(!map?.yaml_path&&!$('fallbackWidth').value){$('advancedImport').open=true;$('fallbackOptions').open=true;}
      throw e;
    }finally{busy(false);}
  });
  $('sshConnect').onclick=()=>run(connect);$('sshDisconnect').onclick=()=>run(async()=>{status(await ssh('disconnect',{}));await buildTree();message('已断开。当前预览保留在本机。');});$('sshForget').onclick=()=>run(async()=>{status(await ssh('forget',{}));$('sshPassword').value='';await buildTree();message('已忘记当前登录信息。');});
  $('remoteRefresh').onclick=()=>run(()=>buildTree($('remoteDirectory').value));$('remoteDirectory').onkeydown=e=>{if(e.key==='Enter')run(()=>buildTree($('remoteDirectory').value));};$('remoteUp').onclick=()=>run(async()=>{status(await ssh('status'));await buildTree();});
  $('previewFormat').onchange=()=>{if(lastPath&&/\.(csv|txt)$/i.test(lastPath))run(()=>open(lastPath));};
  $('remoteSave').onclick=()=>run(async()=>{if(!connected)throw Error('请先连接 Jetson。');if(state.busy)throw Error('请等待计算完成。');const key=$('remoteSource').value,fs=['speed','pp','mppi'].includes(key)?await window.speedSystem.prepare():key==='edited'?state.editedFiles:key==='speed'?(state.result?.files||state.speedOnly?.files):(state.result?.files||state.track?.files),url=fs?.[key];if(!url)throw Error('尚无所选规划结果。文件预览不会生成新的 CSV。');const payload={source:url,path:$('remoteTarget').value.trim()};if(!payload.path)throw Error('请填写目标文件路径。');let result;try{result=await ssh('save',payload);}catch(e){if(!e.data?.revision)throw e;if(!window.i18n.confirm(`用已生成的规划结果覆盖文件？\n${e.data.path}\n将先自动备份旧文件。`))return;result=await ssh('save',{...payload,revision:e.data.revision});}message('已保存：'+result.path+(result.backup?'\n备份：'+result.backup:''));});
  run(async()=>{const d=await ssh('status'),p=d.profile||{};for(const[id,key]of[['sshHost','host'],['sshUser','username'],['sshPort','port']])if(p[key])$(id).value=p[key];if(p.host)$('sshAuto').checked=p.auto_connect===true;status(d);if(connected)await buildTree();else if(p.auto_connect)await connect();else await buildTree();});
})();
