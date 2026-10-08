// Read-only file canvas. Planning state stays separate from previews.
async function openFilePreview(data) {
  if(window.waypointEditor)window.waypointEditor.close();
  const previous=state.preview;
  const next={map:previous?.map||null,route:previous?.route||null,name:data.name,path:data.path,note:data.note};
  if(data.kind==='map') {
    const img=new Image();
    await new Promise((resolve,reject)=>{img.onload=resolve;img.onerror=()=>reject(Error('地图图片无法显示。'));img.src=data.map.url;});
    next.map={...data.map,image:img,path:data.path};
    if(!data.map.resolution)next.route=null;
  } else next.route={points:data.points,path:data.path,count:data.count,format:data.format,importedVelocity:data.velocity,boundaries:data.boundaries||null};
  state.preview=next;state.scale=1;state.pan=[0,0];document.body.classList.add('file-preview-mode');
  $('emptyState').hidden=true;$('trackName').textContent=data.name;$('stageBadge').textContent='文件预览';$('stageBadge').className='badge';
  updatePreviewInfo();draw();say(data.note);
}
function updatePreviewInfo(){
  const p=state.preview;if(!p)return;
  $('fileInfo').replaceChildren();
  const rows=[['当前文件',p.path],['显示方式',p.route?'路线坐标 / 米':p.map?.resolution?'地图坐标 / 米':'图片 / 像素']];
  if(p.route)rows.push(['Waypoints',String(p.route.count)],['CSV 格式',p.route.format]);
  if(p.map)rows.push(['地图',p.map.path],['图像大小',`${p.map.width} × ${p.map.height}`]);
  if(p.map?.resolution)rows.push(['分辨率',p.map.resolution+' m/px'],['地图原点',p.map.origin.join(', ')]);
  if(p.route&&p.map&&!p.map.resolution)rows.push(['提示','地图缺少 YAML，当前仅显示米制路线。打开对应 YAML 后可叠加。']);
  for(const [key,value]of rows){const item=document.createElement('div'),label=document.createElement('small'),text=document.createElement('p');label.textContent=key;text.textContent=value;item.append(label,text);$('fileInfo').append(item);}
  $('clearPreviewMap').hidden=!p.map;$('backToPlanning').hidden=!state.track;
  $('plotInfo').textContent=p.route?`${p.route.count} 个 waypoints · 米制坐标 · 只读预览`:p.map?.resolution?`${p.map.width} × ${p.map.height} · ${p.map.resolution} m/px`:'图片预览 · 像素坐标';
}
function drawFilePreview(ctx,w,h,p=state.preview){
  const map=p.map,route=p.route?.points;
  if(!p.editing&&p.route?.boundaries)p.boundaries=p.route.boundaries;
  const useMap=map&&(!route||map.resolution);
  let minx=Infinity,maxx=-Infinity,miny=Infinity,maxy=-Infinity;
  const include=([x,y])=>{minx=Math.min(minx,x);maxx=Math.max(maxx,x);miny=Math.min(miny,y);maxy=Math.max(maxy,y);};
  if(route)route.forEach(include);
  if(p.boundaries)for(const line of p.boundaries)line.forEach(include);
  let origin=[0,0,0],res=1;
  if(useMap){origin=map.origin||origin;res=map.resolution||1;const c=Math.cos(origin[2]),s=Math.sin(origin[2]);for(const [x,y] of [[0,0],[map.width*res,0],[0,map.height*res],[map.width*res,map.height*res]])include([origin[0]+x*c-y*s,origin[1]+x*s+y*c]);}
  if(!Number.isFinite(minx))return;
  if(p.bounds)({minx,maxx,miny,maxy}=p.bounds);
  const scale=Math.min((w-65)/Math.max(maxx-minx,.1),(h-155)/Math.max(maxy-miny,.1))*state.scale;
  const cx=(minx+maxx)/2,cy=(miny+maxy)/2,ox=w/2+state.pan[0],oy=h/2+25+state.pan[1];
  const screen=([x,y])=>[ox+(x-cx)*scale,oy-(y-cy)*scale];
  if(useMap&&$('showMap').checked){ctx.save();ctx.translate(...screen(origin));ctx.rotate(-origin[2]);ctx.scale(scale*res,scale*res);ctx.drawImage(map.image,0,-map.height);ctx.restore();}
  if(p.boundaries&&(!p.editing||$('editBoundary').checked)){
    const [right,left]=p.boundaries;
    ctx.beginPath();right.concat(left.slice().reverse()).forEach((pt,i)=>{const q=screen(pt);i?ctx.lineTo(...q):ctx.moveTo(...q);});ctx.closePath();ctx.fillStyle='#6a95bc20';ctx.fill();
    for(const line of p.boundaries){ctx.beginPath();line.forEach((pt,i)=>{const q=screen(pt);i?ctx.lineTo(...q):ctx.moveTo(...q);});ctx.closePath();ctx.lineWidth=1.6;ctx.strokeStyle='#90a6bd';ctx.stroke();}
  }
  if(route&&$('showRoute').checked){if(window.editMode!=='speed'){ctx.beginPath();route.forEach((point,i)=>{const q=screen(point);i?ctx.lineTo(...q):ctx.moveTo(...q);});if(p.route.closed)ctx.closePath();ctx.strokeStyle='#21b99e';ctx.lineWidth=2;ctx.stroke();
    if(route.length<=2000){ctx.fillStyle='#20bba0';for(const point of route){ctx.beginPath();ctx.arc(...screen(point),2,0,Math.PI*2);ctx.fill();}}}
    window.speedSystem?.paint(ctx,screen);ctx.fillStyle='#ffba76';ctx.beginPath();ctx.arc(...screen(route[0]),5,0,Math.PI*2);ctx.fill();ctx.font='11px system-ui';const first=screen(route[0]);ctx.fillText('START',first[0]+9,first[1]-9);
  }
  return {scale,cx,cy,ox,oy,screen,bounds:{minx,maxx,miny,maxy}};
}
$('clearPreviewMap').onclick=()=>{if(!state.preview)return;if(state.preview.route){state.preview.map=null;updatePreviewInfo();draw();}else{state.preview=null;document.body.classList.remove('file-preview-mode');$('clearPreviewMap').hidden=true;$('fileInfo').textContent='从左侧打开地图或路线。';if(state.track){$('trackName').textContent=state.track.name;$('stageBadge').textContent='规划工作区';draw();}else{$('emptyState').hidden=false;$('trackName').textContent='打开地图或路线';$('stageBadge').textContent='等待打开';draw();}}};
$('backToPlanning').onclick=()=>{state.preview=null;document.body.classList.remove('file-preview-mode');$('backToPlanning').hidden=true;$('clearPreviewMap').hidden=true;$('trackName').textContent=state.track?.name||'打开地图或路线';$('stageBadge').textContent='规划工作区';draw();};
