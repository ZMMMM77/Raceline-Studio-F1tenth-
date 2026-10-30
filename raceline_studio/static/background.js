(() => {
  let original=null,url=null;
  let layers={},generation=0;
  const select=$('backgroundChoice');
  const layerNames={cleaned:'清理副本（坐标叠加）',changes:'清理改动（坐标叠加）',distance:'距离场（坐标叠加）'};
  function mapLayers(){
    const active=!state.preview&&!window.waypointEditor?.active;
    for(const key of Object.keys(layerNames)){const option=select.querySelector(`[value="${key}"]`);if(option){option.disabled=!active;option.hidden=!active;}}
    if(layerNames[select.value]&&!active)select.value='map';
    return active;
  }
  function loadLayers(data){
    const token=++generation;layers={};
    select.querySelectorAll('[data-preprocessing]').forEach(option=>option.remove());
    for(const [key,label] of Object.entries(layerNames)){
      if(!data?.[key])continue;
      const option=document.createElement('option');option.value=key;option.textContent=label;option.dataset.preprocessing='true';select.append(option);
      const img=new Image();img.onload=()=>{if(token===generation){layers[key]=img;draw();}};
      img.onerror=()=>{if(token===generation){option.remove();if(select.value===key)select.value='map';draw();}};img.src=data[key];
    }
  }
  function available(){return state.preview?.map?.image||original||state.image;}
  function update(){mapLayers();const has=!!available();select.querySelector('[value="original"]').disabled=!has;$('backgroundHint').textContent=select.value==='changes'?'绿色：填孔；橙色：补缝。原图仍用于约束。':select.value==='distance'?'紫色近墙，黄色远墙；清理副本的距离场。':select.value==='cleaned'?'仅用于中心线提取；原图仍用于约束。':select.value==='original'?'原图预览 · 像素坐标':select.value==='none'?'仅显示路线与边界':(state.preview?.map?.resolution||state.track?.map)?'按地图坐标叠加':'未载入带坐标的背景图';}
  function apply(){if(select.value==='original'&&!available())select.value='map';$('showMap').checked=select.value!=='none';draw();}
  select.onchange=apply;$('showMap').addEventListener('change',()=>{select.value=$('showMap').checked?'map':'none';draw();});
  window.backgroundPicker={mapImage:fallback=>layers[select.value]||fallback,load:source=>{loadLayers(state.track?.preprocessing);url=source;original=null;select.value='map';$('showMap').checked=true;if(source){const img=new Image();img.onload=()=>{if(url===source){original=img;draw();}};img.src=source;}update();},draw:(ctx,w,h)=>{update();if(select.value!=='original')return false;const img=available();if(!img)return false;const scale=Math.min((w-40)/img.width,(h-130)/img.height)*state.scale;ctx.drawImage(img,(w-img.width*scale)/2+state.pan[0],(h-img.height*scale)/2+30+state.pan[1],img.width*scale,img.height*scale);ctx.fillStyle='#a7bdd5';ctx.font='11px system-ui';ctx.fillText('原始图片预览 · 切回“当前地图”继续编辑路线',18,h-45);return true;}};
  // Pixel previews must not send drag events to hidden metre-coordinate waypoints.
  const c=$('trackCanvas');for(const type of ['pointerdown','pointermove','pointerup','pointercancel'])c.addEventListener(type,e=>{if(select.value!=='original')return;e.stopImmediatePropagation();},true);
  update();
})();
