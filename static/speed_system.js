(() => {
  const keys=['v_min','v_max','a_max','a_brake','mu_min','mu_max','width'];
  const cache=new WeakMap();let current=null,timer=null,hover=-1;
  const params=()=>Object.fromEntries(keys.map(k=>[k,Number($(k).value)]));
  function target(){const e=window.waypointEditor;if(e?.active)return[e.scene.route,e.scene.route.points,'编辑副本'];if(state.preview)return state.preview.route?[state.preview.route,state.preview.route.points,'预览 CSV']:null;if(state.result)return[state.result,state.result.route,'优化轨迹'];return state.track?[state.track,state.track.center,'中心线']:null;}
  const color=value=>{const ratio=Math.max(0,Math.min(1,value));const r=ratio<.5?1:1-(ratio-.5)*2,g=ratio<.5?ratio*2:1,b=ratio>.7?(ratio-.7)/.3:0;return `rgb(${Math.round(r*220)},${Math.round(g*220)},${Math.round(b*180)})`;};
  function recolor(c){c.colors=c.data.ratio.map(color);}
  function entry(){const t=target();if(!t)return null;let c=cache.get(t[0]);if(!c){c={object:t[0],points:t[1],label:t[2],friction:t[1].map(()=>params().mu_min),history:[],signature:'',data:null,files:null};const seed=t[0].importedVelocity;if(seed){if(seed.parameters)for(const k of keys)if(seed.parameters[k]!=null)$(k).value=seed.parameters[k];if(seed.friction?.length===c.points.length)c.friction=seed.friction.slice();if(seed.ratio)c.seedRatio=seed.ratio.slice();else if(seed.speed){const p=params();c.seedRatio=seed.speed.map(v=>Math.max(0,Math.min(1,(v-p.v_min)/(p.v_max-p.v_min||1))));}}cache.set(t[0],c);}c.points=t[1];return c;}
  function signature(c){return JSON.stringify([c.points,Object.fromEntries(Object.entries(params()).filter(([k])=>k!=='width')),c.friction]);}
  function valid(c){return c?.data&&c.signature===signature(c);}
  function sync(){const c=entry();current=c;
    if(c){if(c.friction.length!==c.points.length){const old=c.friction;c.friction=c.points.map((_,i)=>old[Math.min(old.length-1,Math.floor(i*old.length/c.points.length))]);}
      const sig=signature(c);if(c.signature!==sig&&c.pending!==sig&&c.failed!==sig){c.data=null;c.files=null;c.history=[];c.pending=sig;clearTimeout(c.timer);c.timer=setTimeout(()=>compute(c,sig),180);}}
    render();
  }
  async function compute(c,sig=signature(c)){
    const token=c.token=(c.token||0)+1;c.pending=sig;c.files=null;c.data=null;render();
    try{const data=await api('/api/velocity/profile',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({points:c.points,friction:c.friction,parameters:params(),...(c.seedRatio?{ratio:c.seedRatio}:{})})});if(c.token!==token||signature(c)!==sig)return;c.data=data;recolor(c);c.seedRatio=null;c.signature=sig;c.failed=null;
    }catch(e){if(c.token===token&&signature(c)===sig){c.failed=sig;$('velocityNote').textContent=e.message;}}
    finally{if(c.token===token&&c.pending===sig)c.pending=null;draw();}
  }
  function render(){const [ctx,w,h]=canvasContext('speedCanvas');ctx.clearRect(0,0,w,h);const c=entry(),ok=valid(c),d=ok?c.data:null;window.workflow?.update();
    ['exportPP','exportMPPI','exportSpeed','exportSpeedPNG'].forEach(id=>$(id).disabled=!ok);
    $('generateSpeed').disabled=!c||!!c.pending||state.busy;
    const selected=window.waypointEditor?.active?window.waypointEditor.selection.size:0;
    ['speedDown','speedUp','speedScale','muLow','muHigh'].forEach(id=>$(id).disabled=!ok||!selected);
    $('speedUndo').disabled=!ok||!c.history.length;
    ctx.font='11px system-ui';ctx.fillStyle='#93a9c4';
    if(!d){$('speedCaption').textContent=c?(c.failed?'速度参数或路径无效，请修改后重算':'正在计算当前路径速度…'):'打开路线后显示速度曲线';ctx.fillText('速度 / m/s',12,22);return;}
    const v=d.speed,lo=Math.min(...v),hi=Math.max(...v),p=d.parameters;
    $('speedRange').textContent=`${lo.toFixed(2)}–${hi.toFixed(2)} m/s`;
    $('speedCaption').textContent=`${c.label} · ${v.length} 点 · ${lo.toFixed(2)}–${hi.toFixed(2)} m/s · 估算 ${d.lap_time.toFixed(2)} s${c.manual?' · 手动调速':''}`;
    const x=s=>48+(w-68)*s/d.length,y=v=>h-28-(h-50)*v/(p.v_max*1.1);
    ctx.lineWidth=1;for(let i=0;i<=4;i++){const val=p.v_max*i/4;ctx.strokeStyle='#ffffff12';ctx.beginPath();ctx.moveTo(48,y(val));ctx.lineTo(w-20,y(val));ctx.stroke();ctx.fillStyle='#93a9c4';ctx.fillText(val.toFixed(1),10,y(val)+4);}
    ctx.fillText('m/s',10,12);ctx.fillText('0 m',48,h-8);ctx.fillText(d.length.toFixed(1)+' m',w-68,h-8);
    for(let i=0;i<v.length;i++){const j=(i+1)%v.length;ctx.strokeStyle=c.colors[i];ctx.lineWidth=2.4;ctx.beginPath();ctx.moveTo(x(d.s[i]),y(v[i]));ctx.lineTo(x(j?d.s[j]:d.length),y(v[j]));ctx.stroke();if(window.waypointEditor?.active&&window.waypointEditor.selection.has(i)){ctx.fillStyle='#fff';ctx.beginPath();ctx.arc(x(d.s[i]),y(v[i]),3,0,2*Math.PI);ctx.fill();}}
    if(hover>=0&&hover<v.length){const i=hover;ctx.fillStyle='#fff';ctx.fillText(`#${i+1} · ${v[i].toFixed(3)} m/s · 比例 ${d.ratio[i].toFixed(3)} · μ ${c.friction[i].toFixed(2)}`,70,14);ctx.beginPath();ctx.arc(x(d.s[i]),y(v[i]),4,0,Math.PI*2);ctx.fill();}
  }
  function paint(ctx,screen){const c=entry();if(!valid(c)||!$('showSpeed').checked||!$('showRoute').checked)return;ctx.lineWidth=2.7;for(let i=0;i<c.points.length;i++){ctx.strokeStyle=c.colors[i];ctx.beginPath();ctx.moveTo(...screen(c.points[i]));ctx.lineTo(...screen(c.points[(i+1)%c.points.length]));ctx.stroke();}}
  function remember(c){c.history.push({data:structuredClone(c.data),friction:c.friction.slice(),manual:c.manual});if(c.history.length>40)c.history.shift();c.files=null;}
  function selected(){const c=entry(),e=window.waypointEditor;if(!valid(c)||!e?.active||!e.selection.size)throw Error('请先在 Waypoint 编辑器中选中一个或多个节点。');return[c,[...e.selection]];}
  function scale(factor){try{const [c,indices]=selected();remember(c);const d=c.data,p=d.parameters;indices.forEach(i=>d.ratio[i]=Math.max(0,Math.min(1,d.ratio[i]*factor)));d.speed=d.ratio.map(r=>p.v_min+r*(p.v_max-p.v_min));d.lap_time=d.speed.reduce((sum,v,i)=>{const j=(i+1)%d.speed.length,ds=(j?d.s[j]:d.length)-d.s[i];return sum+ds/Math.max(.1,(v+d.speed[j])/2);},0);recolor(c);c.manual=true;$('velocityNote').textContent=`已调整 ${indices.length} 点的速度比例。手动调整可能超出加速、制动或抓地限制；重算整圈会覆盖手动比例。`;draw();}catch(e){say(e.message,true);}}
  async function friction(high){try{const [c,indices]=selected();remember(c);indices.forEach(i=>c.friction[i]=params()[high?'mu_max':'mu_min']);c.manual=false;await compute(c);$('velocityNote').textContent=`已设置 ${indices.length} 点的摩擦系数，并重新计算整圈速度。`;}catch(e){say(e.message,true);}}
  async function prepare(){const c=entry();if(!valid(c))throw Error('请等待当前路径的速度计算完成。');if(c.files)return c.files;const sig=signature(c),ratio=JSON.stringify(c.data.ratio);const r=await api('/api/velocity/export',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({points:c.points,parameters:params(),ratio:c.data.ratio,friction:c.friction})});if(entry()!==c||signature(c)!==sig||JSON.stringify(c.data.ratio)!==ratio)throw Error('路径或速度已改变，请重新导出。');c.files=r.files;$('outputPath').value=r.output_dir;$('copyPath').disabled=false;return c.files;}
  async function download(key){try{const files=await prepare();const a=document.createElement('a');a.href=files[key]+'?download=1';a.download='';a.click();}catch(e){say(e.message,true);}}
  $('generateSpeed').onclick=()=>{const c=entry();if(c){c.manual=false;c.seedRatio=null;c.history=[];compute(c);}};
  keys.forEach(k=>$(k).addEventListener('change',()=>{const c=entry();if(c)c.files=null;if(c&&['mu_min','mu_max'].includes(k)&&c.data){const old=c.data.parameters[k];c.friction=c.friction.map(v=>v===old?params()[k]:v);}draw();}));
  $('speedDown').onclick=()=>scale(.95);$('speedUp').onclick=()=>scale(1.05);$('speedFactor').oninput=()=>{$('speedScale').textContent='应用倍率 ×'+Number($('speedFactor').value).toFixed(2);};$('speedScale').onclick=()=>scale(Number($('speedFactor').value));$('muLow').onclick=()=>friction(false);$('muHigh').onclick=()=>friction(true);
  $('speedUndo').onclick=()=>{const c=entry(),old=c?.history.pop();if(old){Object.assign(c,old);recolor(c);c.signature=signature(c);c.files=null;draw();}};
  for(const [id,key]of [['exportPP','pp'],['exportMPPI','mppi'],['exportSpeed','speed'],['exportSpeedPNG','speed_png']])$(id).onclick=()=>download(key);
  $('speedCanvas').onpointermove=e=>{const c=entry();if(!valid(c))return;const r=e.currentTarget.getBoundingClientRect(),s=(e.clientX-r.left-48)/(r.width-68)*c.data.length;hover=c.data.s.reduce((best,v,i)=>Math.abs(v-s)<Math.abs(c.data.s[best]-s)?i:best,0);render();};$('speedCanvas').onpointerleave=()=>{hover=-1;render();};
  window.speedSystem={sync,render,paint,prepare,status:()=>{const c=entry();return {ready:!!valid(c),pending:!!c?.pending,manual:!!c?.manual,count:c?.points.length||0,label:c?.label||null};},inherit:(source,dest)=>{const c=cache.get(source);if(valid(c)){dest.importedVelocity={ratio:c.data.ratio.slice(),friction:c.friction.slice(),parameters:{...c.data.parameters}};}},pointColor:i=>{const c=current;return c?.data&&$('showSpeed').checked?c.colors[i]:null;}};sync();
})();
