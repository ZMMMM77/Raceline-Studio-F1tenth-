(() => {
  let working=false,connected=false,lastPath=null,remoteRoots=[],identity=null;
  function message(text,error=false){$('remoteMessage').textContent=text;$('remoteMessage').classList.toggle('error',error);}
  async function requestJSON(prefix,action,body){const r=await fetch(prefix+action,{method:body===undefined?'GET':'POST',headers:{'X-Raceline-Local':'1','Content-Type':'application/json'},...(body===undefined?{}:{body:JSON.stringify(body)})});const d=await r.json();if(!r.ok){const e=Error(d.error||'请求失败');e.data=d;throw e;}return d;}
  const ssh=(action,body)=>requestJSON('/api/remote/',action,body);
  const files=ssh;
  async function run(fn){if(working)return;working=true;const buttons=[...document.querySelectorAll('.connection-settings button,.remote-path button,.explorer-toolbar button,#remoteSave')],disabled=buttons.map(b=>b.disabled);buttons.forEach(b=>b.disabled=true);try{await fn();}catch(e){message(e.message,true);}finally{working=false;buttons.forEach((b,i)=>b.disabled=disabled[i]);}}
  function resetPreview(){window.waypointEditor?.close();state.preview=null;lastPath=null;document.body.classList.remove('file-preview-mode');$('fileInfo').textContent='从左侧打开地图或路线。';$('clearPreviewMap').hidden=true;$('backToPlanning').hidden=true;$('emptyState').hidden=!!state.track;$('trackName').textContent=state.track?.name||'打开地图或路线';$('stageBadge').textContent=state.track?'规划工作区':'等待打开';draw();}
  function status(d){connected=d.connected;remoteRoots=d.directories||[];$('remoteStatus').textContent=connected?`${d.identity.username}@${d.identity.host}`:'未连接 · 设置 SSH';$('remoteDot').classList.toggle('connected',connected);if(connected)document.querySelector('.connection-settings').open=false;const next=JSON.stringify(d.identity);if(connected&&identity&&identity!==next)resetPreview();if(connected)identity=next;}
  function settings(){return{host:$('sshHost').value.trim(),username:$('sshUser').value.trim(),port:Number($('sshPort').value),password:$('sshPassword').value,auto_connect:$('sshAuto').checked,directory:remoteRoots[0]?.path||'~'};}
  async function connect(){message('正在连接 Jetson…');const d=settings();let result;try{result=await ssh('connect',d);}catch(e){if(!e.data?.fingerprint)throw e;if(!confirm(`首次连接 ${d.host}，请核对主机指纹：\n${e.data.fingerprint}\n\n信任此主机？`)){message('已取消连接。');return;}result=await ssh('connect',{...d,fingerprint:e.data.fingerprint});}finally{$('sshPassword').value='';}status(result);await buildTree();}
  async function open(path){if(state.busy)throw Error('请等待当前计算完成。');message('正在打开 '+path.split('/').pop()+'…');const d=await files('preview',{path,format:$('previewFormat').value});await openFilePreview(d);lastPath=path;if(d.kind==='route')$('remoteTarget').value=path;document.querySelectorAll('.remote-entry').forEach(b=>b.classList.toggle('selected',b.dataset.path===path));message(d.note);}
  function branch(name,path,isDirectory,depth=0){
    const item=document.createElement('div'),b=document.createElement('button');b.className='remote-entry';b.dataset.path=path;b.title=path;b.style.paddingLeft=(7+depth*13)+'px';b.classList.toggle('selected',path===lastPath);
    const icon=document.createElement('span');icon.className='file-icon';icon.textContent=isDirectory?'▸':/\.(csv|txt)$/i.test(name)?'CSV':/\.ya?ml$/i.test(name)?'YML':'IMG';
    const label=document.createElement('span');label.className='file-name';label.textContent=name;b.append(icon,label);item.append(b);
    if(isDirectory){const children=document.createElement('div');children.hidden=true;item.append(children);b.setAttribute('aria-expanded','false');let loaded=false;
      async function toggle(){if(!children.hidden){children.hidden=true;icon.textContent='▸';b.setAttribute('aria-expanded','false');return;}if(!loaded){const d=await files('list',{path});for(const e of d.entries){if(!e.directory&&!/\.(csv|txt|yaml|yml|png|pgm|jpg|jpeg)$/i.test(e.name))continue;children.append(branch(e.name,e.path||d.path.replace(/\/$/,'')+'/'+e.name,e.directory,depth+1).item);}if(!children.childElementCount){const empty=document.createElement('p');empty.className='tree-empty';empty.textContent='没有地图或路线文件';children.append(empty);}loaded=true;}children.hidden=false;icon.textContent='▾';b.setAttribute('aria-expanded','true');}
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
  $('sshConnect').onclick=()=>run(connect);$('sshDisconnect').onclick=()=>run(async()=>{status(await ssh('disconnect',{}));await buildTree();message('已断开。当前预览保留在本机。');});$('sshForget').onclick=()=>run(async()=>{status(await ssh('forget',{}));$('sshPassword').value='';await buildTree();message('已忘记当前登录信息。');});
  $('remoteRefresh').onclick=()=>run(()=>buildTree($('remoteDirectory').value));$('remoteDirectory').onkeydown=e=>{if(e.key==='Enter')run(()=>buildTree($('remoteDirectory').value));};$('remoteUp').onclick=()=>run(async()=>{status(await ssh('status'));await buildTree();});
  $('previewFormat').onchange=()=>{if(lastPath&&/\.(csv|txt)$/i.test(lastPath))run(()=>open(lastPath));};
  $('remoteSave').onclick=()=>run(async()=>{if(!connected)throw Error('请先连接 Jetson。');if(state.busy)throw Error('请等待计算完成。');const key=$('remoteSource').value,fs=['speed','pp','mppi'].includes(key)?await window.speedSystem.prepare():key==='edited'?state.editedFiles:key==='speed'?(state.result?.files||state.speedOnly?.files):(state.result?.files||state.track?.files),url=fs?.[key];if(!url)throw Error('尚无所选规划结果。文件预览不会生成新的 CSV。');const payload={source:url,path:$('remoteTarget').value.trim()};if(!payload.path)throw Error('请填写目标文件路径。');let result;try{result=await ssh('save',payload);}catch(e){if(!e.data?.revision)throw e;if(!confirm(`用已生成的规划结果覆盖文件？\n${e.data.path}\n将先自动备份旧文件。`))return;result=await ssh('save',{...payload,revision:e.data.revision});}message('已保存：'+result.path+(result.backup?'\n备份：'+result.backup:''));});
  run(async()=>{const d=await ssh('status'),p=d.profile||{};for(const[id,key]of[['sshHost','host'],['sshUser','username'],['sshPort','port']])if(p[key])$(id).value=p[key];if(p.host)$('sshAuto').checked=p.auto_connect===true;status(d);if(connected)await buildTree();else if(p.auto_connect)await connect();else await buildTree();});
})();
