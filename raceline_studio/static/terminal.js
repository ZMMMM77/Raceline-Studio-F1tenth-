/* A shared bottom dock; switching tabs never stops a Jetson process. */
(() => {
  const el = id => document.getElementById(id);
  const chart = document.querySelector('.velocity-chart');
  const originalHeight = chart.getBoundingClientRect().height;
  const heading = chart.firstElementChild;
  const caption = el('speedCaption');
  const canvas = el('speedCanvas');
  let config = {name:'Jetson',tasks:[]}, selected = '', sessions = [], connected = false;
  let mode = 'speed', busy = false, polling = false, revision = 0, draft = null, lastOutput = '', pollTimer;
  const en = () => window.i18n?.language() === 'en';
  const tr = (zh, english) => en() ? english : zh;
  const label = (zh, english) => `<span data-term-zh="${zh}" data-term-en="${english}">${tr(zh,english)}</span>`;
  const errors = {
    SSH_DISCONNECTED:['请先在左栏连接 Jetson。','Connect to Jetson in the left sidebar first.'],
    TMUX_MISSING:['Jetson 未安装 tmux，请在 Jetson 终端运行：sudo apt install tmux','tmux is missing on Jetson. Run there: sudo apt install tmux'],
    EMPTY_COMMAND:['请先在配置中填写启动命令。','Set a launch command in Settings first.'],
    NOT_RUNNING:['当前终端未运行。','This terminal is not running.'],
    STOP_BEFORE_REMOVE:['请先停止要删除的终端，再保存配置。','Stop the terminal before removing its configuration.'],
    INVALID_CONFIG:['配置无效，请检查字段长度和终端数量（最多 12 个）。','Invalid settings. Check field lengths and the 12-terminal limit.'],
    TERMINAL_REQUEST_FAILED:['终端请求失败，请检查 SSH 连接后重试。启动请求中断时先刷新状态，避免重复启动。','Terminal request failed. Check SSH and retry. Refresh status after an interrupted launch.']
  };
  const message = text => {el('terminalNotice').textContent=text;};
  function errorText(text) {for(const [key, pair] of Object.entries(errors)) text=text.replaceAll(key,tr(...pair));return text;}
  async function api(path, data) {
    const response=await fetch('/api/terminals/'+path, data === undefined ? {} : {method:'POST',headers:{'Content-Type':'application/json','X-Raceline-Local':'1'},body:JSON.stringify(data)});
    const result=await response.json();if(!response.ok)throw new Error(errorText(result.error||'TERMINAL_REQUEST_FAILED'));return result;
  }
  chart.style.setProperty('--dock-height', `${originalHeight}px`);
  chart.classList.add('terminal-dock');
  heading.className='dock-heading';
  heading.querySelector('h2').remove();
  const tabs=document.createElement('div');tabs.className='dock-tabs terminal-owned';tabs.setAttribute('role','tablist');
  tabs.innerHTML=`<button id="dockSpeed" role="tab" aria-selected="true" aria-controls="dockSpeedPane">${label('速度曲线','Speed curve')}</button><button id="dockTerminal" role="tab" aria-selected="false" aria-controls="dockTerminalPane">${label('节点终端','Node terminals')}</button>`;
  heading.prepend(tabs);
  const toolbar=document.createElement('div');toolbar.id='terminalToolbar';toolbar.className='terminal-owned';toolbar.hidden=true;
  toolbar.innerHTML=`<span id="terminalProfile"></span><button id="terminalStartAll">${label('▶ 一键启动','▶ Start all')}</button><button id="terminalSettings">${label('配置','Settings')}</button><button id="terminalExpand" title="Expand / restore">⤢</button>`;
  heading.append(toolbar);
  const speedPane=document.createElement('div');speedPane.id='dockSpeedPane';speedPane.setAttribute('role','tabpanel');speedPane.append(canvas);chart.append(speedPane);
  const terminal=document.createElement('div');terminal.id='dockTerminalPane';terminal.className='terminal-owned';terminal.setAttribute('role','tabpanel');terminal.hidden=true;
  terminal.innerHTML=`<div class="terminal-session-bar"><div id="terminalSessions" role="tablist"></div><div id="terminalNotice" role="status"></div><button id="terminalStart">${label('启动','Start')}</button><button id="terminalStop" title="Ctrl+C">${label('停止','Stop')}</button></div><pre id="terminalOutput" tabindex="0" aria-label="Jetson terminal output"></pre><form id="terminalInputForm"><span>❯</span><input id="terminalInput" autocomplete="off" aria-label="Terminal input"><button type="submit">↵</button></form>`;
  chart.append(terminal);
  const dialog=document.createElement('dialog');dialog.id='terminalConfig';dialog.className='terminal-owned';
  dialog.innerHTML=`<form id="terminalConfigForm"><div class="terminal-dialog-header"><h2>${label('节点终端配置','Node terminal settings')}</h2><button type="button" id="terminalConfigClose">×</button></div><label>${label('组合名称','Profile name')}<input id="terminalConfigName" maxlength="60"></label><p>${label('命令在 Jetson 上执行。勾选的终端按列表顺序发出启动命令，不等待节点就绪。','Commands run on Jetson. Checked terminals launch in list order, without waiting for readiness.')}</p><div id="terminalConfigRows"></div><button type="button" id="terminalAdd">${label('＋ 添加终端','＋ Add terminal')}</button><p>${label('关闭网页或切回速度曲线不会停止节点。就绪关键词仅匹配近期输出，不代表 ROS 数据已验证。','Closing this page or switching tabs keeps nodes running. A readiness keyword only matches recent output; it does not verify ROS data.')}</p><p>${label('配置仅保存在本机，不上传 GitHub。请勿在命令中填写密码。支持普通命令输入，暂不支持 vim 等全屏终端程序。','Settings stay on this computer and are excluded from GitHub. Do not put passwords in commands. Line input is supported; full-screen programs such as vim are not.')}</p><div id="terminalConfigError" role="alert"></div><footer><button type="button" id="terminalConfigCancel">${label('取消','Cancel')}</button><button type="submit" id="terminalConfigSave">${label('保存配置','Save settings')}</button></footer></form>`;
  [tabs,toolbar,terminal,dialog].forEach(node=>node.setAttribute('data-no-translate',''));
  document.body.append(dialog);
  function localize(){document.querySelectorAll('[data-term-zh]').forEach(n=>n.textContent=en()?n.dataset.termEn:n.dataset.termZh);renderSessions();}
  function switchMode(next){
    mode=next;const terminalMode=mode==='terminal';
    el('dockSpeed').setAttribute('aria-selected',String(!terminalMode));el('dockTerminal').setAttribute('aria-selected',String(terminalMode));
    el('dockSpeedPane').hidden=terminalMode;terminal.hidden=!terminalMode;toolbar.hidden=!terminalMode;caption.hidden=terminalMode;
    if(!terminalMode){chart.classList.remove('expanded');window.drawSpeed?.();}else refresh();
  }
  el('dockSpeed').onclick=()=>switchMode('speed');el('dockTerminal').onclick=()=>switchMode('terminal');
  for(const id of ['dockSpeed','dockTerminal'])el(id).onkeydown=e=>{if(['ArrowLeft','ArrowRight'].includes(e.key)){e.preventDefault();const next=id==='dockSpeed'?'terminal':'speed';switchMode(next);el(next==='speed'?'dockSpeed':'dockTerminal').focus();}};
  el('terminalExpand').onclick=()=>chart.classList.toggle('expanded');
  document.addEventListener('keydown',e=>{if(e.key==='Escape')chart.classList.remove('expanded');});
  const live = s => ['running','ready_log'].includes(s?.state);
  function stateLabel(s){
    if(!connected)return tr('连接中断','Disconnected');
    const names={idle:['未启动','Not started'],running:['运行中','Running'],ready_log:['就绪日志已匹配','Readiness log matched'],exited:['已退出','Exited'],failed:['异常退出','Failed']};
    let name=tr(...(names[s?.state]||names.idle));if(s?.exit_code!=null)name+=` (${s.exit_code})`;if(s?.signal)name+=` · ${s.signal}`;return name;
  }
  function renderSessions(){
    el('terminalProfile').textContent=config.name;
    const holder=el('terminalSessions');const focusedId=document.activeElement?.dataset.task;
    holder.replaceChildren();
    for(const task of config.tasks){const s=sessions.find(v=>v.id===task.id);const button=document.createElement('button');button.type='button';button.dataset.task=task.id;button.setAttribute('role','tab');button.setAttribute('aria-selected',String(selected===task.id));button.title=stateLabel(s);button.className='session-'+(connected?s?.state||'idle':'idle');button.textContent=`● ${task.name}`;button.onclick=()=>{selected=task.id;lastOutput='';el('terminalOutput').textContent='';renderSessions();refresh();};holder.append(button);if(focusedId===task.id)button.focus();}
    if(!config.tasks.length){holder.textContent=tr('点击“配置”添加启动命令','Add launch commands in Settings');}
    const current=sessions.find(v=>v.id===selected);
    el('terminalStartAll').disabled=busy||!connected||!config.tasks.some(t=>t.enabled&&t.command);
    el('terminalStart').disabled=busy||!connected||!selected||live(current);
    el('terminalStop').disabled=busy||!connected||!live(current);
    el('terminalInput').disabled=busy||!connected||!live(current);
    el('terminalSettings').disabled=busy;
  }
  function apply(result, requested){
    sessions=result.sessions;connected=true;renderSessions();
    if(requested===selected){const output=el('terminalOutput');const atBottom=output.scrollTop+output.clientHeight>=output.scrollHeight-12;if(result.output!==lastOutput){output.replaceChildren();for(const line of (result.output||'').split('\n')){const span=document.createElement('span');span.textContent=line+'\n';span.className=/\b(ERROR|FATAL|Traceback)\b/i.test(line)?'log-error':/\b(WARN|WAIT|WARNING)\b/i.test(line)?'log-warning':'';output.append(span);}lastOutput=result.output||'';if(atBottom)output.scrollTop=output.scrollHeight;}}
    const current=sessions.find(s=>s.id===selected);
    message(result.errors?.length ? errorText(result.errors.join(' · ')) : selected ? stateLabel(current) : tr('点击“配置”添加终端；先在左栏连接 Jetson。','Add terminals in Settings; connect to Jetson in the left sidebar.'));
  }
  async function refresh(){
    if(polling||busy||document.hidden||mode!=='terminal')return;
    polling=true;const requested=selected, startedAt=revision;
    try{const result=await api('action',{action:'status',selected:requested});if(!busy&&startedAt===revision)apply(result,requested);}catch(e){if(!busy&&startedAt===revision){connected=false;renderSessions();message(e.message);}}finally{polling=false;}
  }
  async function action(kind,text){
    if(busy)return;
    busy=true;revision++;renderSessions();message(tr('正在请求 Jetson…','Contacting Jetson…'));
    const requested=selected;
    try{apply(await api('action',{action:kind,target:selected,selected,text}),requested);if(kind==='interrupt')message(tr('已发送 Ctrl+C，等待进程退出；若仍运行，可查看日志后重试。','Ctrl+C sent; waiting for exit. If still running, inspect the output before retrying.'));}
    catch(e){message(e.message);}finally{busy=false;renderSessions();}
  }
  el('terminalStartAll').onclick=()=>action('start_all');el('terminalStart').onclick=()=>action('start');el('terminalStop').onclick=()=>action('interrupt');
  el('terminalInputForm').onsubmit=async e=>{e.preventDefault();if(el('terminalInput').disabled)return;const input=el('terminalInput');await action('input',input.value);input.value='';};
  el('terminalInput').onkeydown=e=>{if(e.ctrlKey&&e.key.toLowerCase()==='c'){e.preventDefault();action('interrupt');}};
  function saveDraft(){
    draft.name=el('terminalConfigName').value;
    for(const row of el('terminalConfigRows').children){const task=draft.tasks.find(t=>t.id===row.dataset.id);row.querySelectorAll('[data-field]').forEach(field=>task[field.dataset.field]=field.type==='checkbox'?field.checked:field.value);}
  }
  function renderDraft(){
    const container=el('terminalConfigRows');container.replaceChildren();
    draft.tasks.forEach((task,index)=>{
      const row=document.createElement('fieldset');row.dataset.id=task.id;
      row.innerHTML=`<legend>${tr('终端','Terminal')} ${index+1}</legend><div class="terminal-config-top"><label><input type="checkbox" data-field="enabled">${label('加入一键启动','Include in Start all')}</label><button type="button" data-remove>${label('删除','Remove')}</button></div><div class="terminal-config-fields"><label>${label('名称','Name')}<input data-field="name" maxlength="60" required></label><label>${label('Jetson 工作目录','Jetson working directory')}<input data-field="directory" maxlength="1024" placeholder="~/ros2_ws"></label></div><label>${label('环境准备（如 source，可多行）','Environment setup (source commands, multiple lines)')}<textarea data-field="setup" rows="2" maxlength="8000" spellcheck="false" placeholder="source /opt/ros/…/setup.bash"></textarea></label><label>${label('启动命令','Launch command')}<textarea data-field="command" rows="2" maxlength="16000" spellcheck="false" placeholder="ros2 launch …"></textarea></label><label>${label('就绪日志关键词（可选）','Readiness log keyword (optional)')}<input data-field="ready_text" maxlength="200"></label>`;
      row.querySelectorAll('[data-field]').forEach(field=>{if(field.type==='checkbox')field.checked=task[field.dataset.field];else field.value=task[field.dataset.field];});
      row.querySelector('[data-remove]').onclick=()=>{saveDraft();draft.tasks=draft.tasks.filter(t=>t.id!==task.id);renderDraft();};container.append(row);
    });el('terminalAdd').disabled=draft.tasks.length>=12;
  }
  el('terminalSettings').onclick=()=>{draft=structuredClone(config);el('terminalConfigName').value=draft.name;el('terminalConfigError').textContent='';renderDraft();dialog.showModal();};
  el('terminalAdd').onclick=()=>{saveDraft();draft.tasks.push({id:crypto.randomUUID().replaceAll('-','').slice(0,12),name:tr('新终端','New terminal'),directory:'~',setup:'',command:'',ready_text:'',enabled:true});renderDraft();el('terminalConfigRows').lastElementChild?.scrollIntoView({block:'nearest'});};
  el('terminalConfigClose').onclick=el('terminalConfigCancel').onclick=()=>dialog.close();
  el('terminalConfigForm').onsubmit=async e=>{e.preventDefault();saveDraft();el('terminalConfigSave').disabled=true;try{config=await api('config',draft);if(!config.tasks.some(t=>t.id===selected))selected=config.tasks[0]?.id||'';dialog.close();renderSessions();message(tr('配置已保存。修改将在下次启动时生效。','Settings saved. Changes apply on the next launch.'));refresh();}catch(e){el('terminalConfigError').textContent=e.message;}finally{el('terminalConfigSave').disabled=false;}};
  window.addEventListener('raceline-language-change',localize);
  api('config').then(data=>{config=data;selected=config.tasks[0]?.id||'';renderSessions();}).catch(e=>message(e.message));
  pollTimer=setInterval(refresh,2000);window.addEventListener('pagehide',()=>clearInterval(pollTimer));
  renderSessions();
})();
