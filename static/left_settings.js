(() => {
  function reveal(el){for(let p=el.parentElement;p;p=p.parentElement)if(p.tagName==='DETAILS')p.open=true;el.focus();}
  let requestId=0;
  window.inspectCsv=async function(enforce=false){
    const file=$('csvFile').files[0],id=++requestId;
    if(state.mode!=='csv'||!file)return true;
    try{
      const text=await file.text();if(id!==requestId)return false;
      const lines=text.replace(/^\uFEFF/,'').split(/\r?\n/).map(s=>s.trim()).filter(Boolean),rows=lines.filter(s=>!s.startsWith('#'));
      if(!rows.length)throw Error('CSV 没有数据。');
      const sep=rows[0].split(';').length>rows[0].split(',').length?';':',';
      const split=s=>s.split(sep).map(x=>x.trim().replace(/^"|"$/g,''));
      let header=null;
      if(!Number.isFinite(Number(split(rows[0])[0])))header=split(rows.shift()).map(s=>s.toLowerCase());
      if(!header)for(const line of lines.filter(s=>s.startsWith('#')).reverse()){const fields=split(line.replace(/^#\s*/, '')).map(s=>s.toLowerCase());if((fields.includes('x')&&fields.includes('y'))||(fields.includes('x_m')&&fields.includes('y_m'))){header=fields;break;}}
      if(!rows.length)throw Error('CSV 没有坐标行。');
      const first=split(rows[0]),format=$('csvFormat').value;let ix=0,iy=1,label='两列坐标';
      if(format==='auto'){
        if(header&&(header.includes('x_m')&&header.includes('y_m'))){ix=header.indexOf('x_m');iy=header.indexOf('y_m');label=header.includes('vx_mps')?'按表头 · 实际速度 m/s':header.includes('w_tr_right_m')?'中心线与宽度':'按坐标表头';}
        else if(header&&header.includes('x')&&header.includes('y')){ix=header.indexOf('x');iy=header.indexOf('y');label=header.includes('speed_ratio')?'Pure Pursuit · 速度比例':'按坐标表头';}
        else if(first.length!==2){$('csvDetection').textContent=`此 CSV 有 ${first.length} 列且缺少明确坐标表头，请在高级导入设置中选择列排列。`;if(enforce){reveal($('csvFormat'));say('CSV 列含义不明确，请选择列排列后再导入。',true);}return false;}
      }else{label={pure_pursuit:'Pure Pursuit',mppi:'MPPI',xy_widths:'中心线与宽度'}[format];if(format==='mppi'){ix=1;iy=2;}}
      const preview=rows.slice(0,3).map(row=>{const fields=split(row);const x=Number(fields[ix]),y=Number(fields[iy]);if(!Number.isFinite(x)||!Number.isFinite(y))throw Error('坐标不是有效数字，请检查列排列。');return `(${x.toFixed(2)}, ${y.toFixed(2)})`;}).join('、');
      $('csvDetection').textContent=`已识别：${label} · ${rows.length} 行\n坐标预览：${preview}\n导入规划后重新计算速度。`;return true;
    }catch(e){$('csvDetection').textContent=e.message;if(enforce){reveal($('csvFormat'));say(e.message,true);}return false;}
  };
  $('csvFile').addEventListener('change',()=>window.inspectCsv());$('csvFormat').addEventListener('change',()=>window.inspectCsv());
  // Explicitly saved preferences are separated by purpose; no paths, files or SSH credentials.
  const groups={advancedImport:['csvFormat','previewFormat','fallbackWidth','boundarySource','cleanupMap','cleanupHoleArea','cleanupGapRadius','reverse'],vehicleSettings:['limitMode','angleType','steer','wheelTrack','radius','wheelbase','reference','carWidth','carLength','rearOverhang','margin'],advancedSolver:['nodes','spacing','maxRuntime','plateauWindow','plateauPercent']};
  for(const [id,ids] of Object.entries(groups)){
    const panel=$(id),button=document.createElement('button'),note=document.createElement('p');button.type='button';button.className='subtle full';button.textContent='保存本组设置';note.className='hint';note.setAttribute('role','status');panel.append(button,note);
    try{const saved=JSON.parse(localStorage.getItem('raceline.settings.'+id)||'null');if(saved){for(const key of ids){const el=$(key),value=saved[key];if(value===undefined)continue;if(el.type==='checkbox')el.checked=value===true;else if(typeof value==='string'){if(el.tagName!=='SELECT'||[...el.options].some(o=>o.value===value))el.value=value;}}note.textContent='已恢复本机保存的设置。';}}catch{}
    button.onclick=()=>{for(const key of ids){const el=$(key);if(el.value!==''&&!el.checkValidity()){reveal(el);el.reportValidity();return;}}try{localStorage.setItem('raceline.settings.'+id,JSON.stringify(Object.fromEntries(ids.map(key=>[key,$(key).type==='checkbox'?$(key).checked:$(key).value]))));note.textContent='本组设置已保存到当前浏览器。';}catch{note.textContent='浏览器不允许保存；本次设置仍然有效。';}};
  }
  $('steeringInputs').hidden=$('limitMode').value==='radius';$('radiusInput').hidden=$('limitMode').value!=='radius';$('trackInput').hidden=$('angleType').value!=='inner';updateDerived();
})();
