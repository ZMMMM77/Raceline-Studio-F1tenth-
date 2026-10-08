(() => {
  let original=null,url=null;
  const select=$('backgroundChoice');
  function available(){return state.preview?.map?.image||original||state.image;}
  function update(){const has=!!available();select.querySelector('[value="original"]').disabled=!has;$('backgroundHint').textContent=select.value==='original'?'原图预览 · 像素坐标':select.value==='none'?'仅显示路线与边界':(state.preview?.map?.resolution||state.track?.map)?'按地图坐标叠加':'未载入带坐标的背景图';}
  function apply(){if(select.value==='original'&&!available())select.value='map';$('showMap').checked=select.value!=='none';draw();}
  select.onchange=apply;$('showMap').addEventListener('change',()=>{select.value=$('showMap').checked?'map':'none';draw();});
  window.backgroundPicker={load:source=>{url=source;original=null;select.value='map';$('showMap').checked=true;if(source){const img=new Image();img.onload=()=>{if(url===source){original=img;draw();}};img.src=source;}update();},draw:(ctx,w,h)=>{update();if(select.value!=='original')return false;const img=available();if(!img)return false;const scale=Math.min((w-40)/img.width,(h-130)/img.height)*state.scale;ctx.drawImage(img,(w-img.width*scale)/2+state.pan[0],(h-img.height*scale)/2+30+state.pan[1],img.width*scale,img.height*scale);ctx.fillStyle='#a7bdd5';ctx.font='11px system-ui';ctx.fillText('原始图片预览 · 切回“当前地图”继续编辑路线',18,h-45);return true;}};
  // Pixel previews must not send drag events to hidden metre-coordinate waypoints.
  const c=$('trackCanvas');for(const type of ['pointerdown','pointermove','pointerup','pointercancel'])c.addEventListener(type,e=>{if(select.value!=='original')return;e.stopImmediatePropagation();},true);
  update();
})();
