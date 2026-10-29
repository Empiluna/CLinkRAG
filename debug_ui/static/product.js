/* Application navigation, actual research events, and a searchable recorded-paper library. */
(() => {
 const defaults={theme:document.documentElement.dataset.theme||'dark',motion:true,font:'normal',graphLimit:10,method:'clinkrag_online',initial:3,tokens:1800};
 let prefs={...defaults};try{prefs={...defaults,...JSON.parse(localStorage.getItem('clinkrag-preferences')||'{}')};}catch{}
 prefs.method='clinkrag_online';
 prefs.graphLimit=[6,10,12].includes(Number(prefs.graphLimit))?Number(prefs.graphLimit):10;
 let screen='home',records=[],snapshot={},library=null,libraryRun='',libraryTicket=0,libraryPage=0,lastRun='';
 const create=(tag,text,cls)=>{const e=document.createElement(tag);if(text!=null)e.textContent=text;if(cls)e.className=cls;return e;};
 const main=$('workspace'),research=create('section');research.id='research-screen';$('research-content').before(research);research.append($('research-content'));
 const screens=create('div');screens.id='application-pages';main.prepend(screens);
 screens.innerHTML=`
 <section id="home-screen" class="app-page">
 <div class="home-entry"><h1>你想研究什么？</h1>
 <form id="home-compose" class="home-compose"><label class="home-input-label" for="home-question">研究问题</label><textarea id="home-question" rows="2" minlength="5" maxlength="4000" required placeholder="输入你的研究问题…"></textarea><div class="home-compose-actions"><button id="home-start" type="submit" aria-label="开始研究" title="开始研究" disabled><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 19V5m-6 6 6-6 6 6"/></svg></button></div></form>
 <div class="home-quick-options"><div class="home-model-picker"><select id="home-model" hidden aria-label="研究模型" disabled><option>正在读取模型…</option></select><button id="home-model-toggle" type="button" aria-haspopup="listbox" aria-expanded="false" aria-controls="home-model-menu" disabled><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3Z"/></svg><span id="home-model-name">读取模型…</span><svg class="model-chevron" viewBox="0 0 24 24" aria-hidden="true"><path d="m8 10 4 4 4-4"/></svg></button><div id="home-model-menu" hidden><div class="model-menu-tools"><span id="home-model-count">模型</span><button id="home-model-refresh" type="button" aria-label="刷新模型列表">刷新</button></div><p id="home-model-status" role="status" hidden></p><div id="home-model-list" role="listbox" aria-label="研究模型"></div></div></div><label id="home-range-wrap" title="检索后，最多选择多少篇论文进入内容分析和关系构建"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h6a3 3 0 0 1 3 3v13a4 4 0 0 0-4-2H4V5Zm16 0h-4a3 3 0 0 0-3 3m0 13a4 4 0 0 1 4-2h3V5Z"/></svg><span class="home-option-caption">研究范围</span><select id="home-range" aria-label="首页最多分析论文数"><option value="6">最多分析 6 篇论文</option><option value="12">最多分析 12 篇论文</option><option value="20">最多分析 20 篇论文</option><option value="30">最多分析 30 篇论文</option><option value="custom">自定义篇数…</option></select></label><label title="回答长度"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 6h14M5 12h14M5 18h8"/></svg><span id="home-length-label" class="home-option-caption">回答长度</span><select id="home-length" aria-label="首页回答长度"></select></label><button id="home-more" type="button"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h9m4 0h3M4 17h3m4 0h9"/><circle cx="15" cy="7" r="2"/><circle cx="9" cy="17" r="2"/></svg><span>更多设置</span></button></div>
 </div></section>
 <section id="records-screen" class="app-page" hidden><div class="page-heading"><div><span class="section-kicker">RESEARCH HISTORY</span><h1>研究记录</h1><p>问题、过程和证据都保留在同一份记录中。</p></div><button id="records-new" class="primary">新建研究</button></div><div class="page-filters"><input id="records-search" type="search" placeholder="搜索研究问题" aria-label="搜索研究记录"><select id="records-status" aria-label="按研究状态筛选"><option value="">全部状态</option><option value="success">已完成</option><option value="running">研究中</option><option value="error">执行失败</option><option value="interrupted">已中断</option><option value="cancelled">已停止</option></select></div><div id="records-list" class="research-cards"></div></section>
 <section id="library-screen" class="app-page" hidden><div class="page-heading"><div><span class="section-kicker">PAPER LIBRARY</span><h1>文献库</h1><p>先用标题和检索状态筛选，再阅读原文或探索关系。</p></div><span id="library-count" class="workspace-chip">选择一项研究</span></div><label for="library-run">文献来自哪次研究</label><select id="library-run"></select><div class="page-filters"><input id="library-search" type="search" placeholder="搜索完整论文标题" aria-label="搜索文献库"><select id="library-scope" aria-label="文献状态"><option value="all">全部已记录</option><option value="retrieved">已找到</option><option value="context">回答证据</option><option value="cited">答案实际引用</option><option value="seed">最先找到</option></select><select id="library-sort" aria-label="文献排序"><option value="evidence">回答证据优先</option><option value="title">标题 A–Z</option></select></div><div id="library-list"></div><div class="directory-pager"><button id="library-prev" class="secondary">上一页</button><span id="library-page"></span><button id="library-next" class="secondary">下一页</button></div></section>
 <section id="settings-screen" class="app-page" hidden><div class="page-heading"><div><span class="section-kicker">PREFERENCES</span><h1>设置</h1><p>按你的阅读习惯调整工作空间，偏好只保存在本机。</p></div><span id="settings-saved" role="status"></span></div><div class="settings-grid">
 <section class="panel settings-card"><h2>阅读与交互</h2><label for="pref-theme">界面主题</label><select id="pref-theme"><option value="dark">深色</option><option value="light">浅色</option></select><label for="pref-font">正文大小</label><select id="pref-font"><option value="normal">标准 · 18 px</option><option value="large">大字 · 20 px</option></select><label class="setting-check"><input id="pref-motion" type="checkbox"> 启用界面过渡动画</label><p class="fine">系统开启“减少动态效果”时优先遵循系统设置。</p></section>
 <section class="panel settings-card"><h2>关系图探索</h2><label for="pref-graph">每组最多展示的论文数</label><select id="pref-graph"><option value="6">6 篇 · 更宽松</option><option value="10">10 篇 · 标准</option><option value="12">12 篇 · 更多关联</option></select><p>每次围绕一篇论文查看直接连接。其余关联可翻页查看，完整论文始终保留在目录中。</p></section>
 <section class="panel settings-card"><h2>新研究默认参数</h2><input id="pref-method" type="hidden" value="clinkrag_online"><div class="parameters"><div><label for="pref-initial">起始证据片段数</label><select id="pref-initial"><option>1</option><option>3</option><option>5</option><option>8</option></select></div><div><label for="pref-tokens">单次生成上限</label><select id="pref-tokens"><option value="1000">1,000 tokens</option><option value="1800">1,800 tokens</option><option value="3000">3,000 tokens</option><option value="6000">6,000 tokens</option><option value="10000">10,000 tokens</option><option value="12000">12,000 tokens</option></select></div></div><p class="fine">应用于新问题，已有草稿和历史运行不会被覆盖。</p></section>
 <section class="panel settings-card"><h2>本地服务</h2><dl id="settings-service"></dl><button id="settings-check" class="secondary">重新检查连接</button><p class="fine">模型与密钥在对应服务分类中设置。</p></section></div><button id="settings-reset" class="text-button">恢复界面和新研究默认设置</button></section>
 <section id="experiments-screen" class="app-page" hidden><div class="page-heading"><div><span class="section-kicker">EVALUATION</span><h1>方法对照</h1><p>检查当前开发实验的结果和适用范围。</p></div></div></section>`;
 const nav=create('nav');nav.className='app-navigation';nav.setAttribute('aria-label','主要功能');
 const routes=[['home','⌂','研究首页'],['research','◉','当前研究'],['records','▤','研究记录'],['library','▥','文献库'],['experiments','◫','方法对照'],['settings','⚙','设置']];
 const bottomNav=create('nav');bottomNav.className='sidebar-bottom-nav';bottomNav.setAttribute('aria-label','工作空间设置');
 const sidebarIcons={home:'m3 10 9-7 9 7v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1Z',library:'M4 4h4v16H4ZM10 4h4v16h-4Zm6 1 4-1 3 15-4 1Z',settings:'M9 3h6l1 3 3 1 2 5-2 5-3 1-1 3H9l-1-3-3-1-2-5 2-5 3-1ZM15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z'};
 for(const [id,,label]of routes.filter(([id])=>['home','library','settings'].includes(id))){
  const b=create('button');b.type='button';b.dataset.screen=id;
  const icon=document.createElementNS('http://www.w3.org/2000/svg','svg');icon.setAttribute('viewBox','0 0 24 24');icon.setAttribute('aria-hidden','true');icon.classList.add('sidebar-nav-icon');
  const path=document.createElementNS(icon.namespaceURI,'path');path.setAttribute('d',sidebarIcons[id]);icon.append(path);
  b.append(icon,create('span',label));b.onclick=()=>open(id);(id==='settings'?bottomNav:nav).append(b);
 }
 $('new-research').after(nav);$('sidebar').append(bottomNav);
 $('history').classList.add('compact-history');document.querySelector('.history-header h2').textContent='最近';$('history').setAttribute('aria-label','历史研究');
 const journey=create('section');journey.id='journey-view';journey.hidden=true;journey.className='journey-view';journey.setAttribute('role','tabpanel');journey.setAttribute('aria-labelledby','journey-tab');
 const story=window.createResearchJourney(journey);
 $('answer-view').before(journey);const tab=create('button','研究过程');tab.id='journey-tab';tab.setAttribute('role','tab');tab.setAttribute('aria-selected','false');tab.setAttribute('aria-controls','journey-view');document.querySelector('[role=tablist]').prepend(tab);tab.onclick=showJourney;
 const liveButton=create('button','查看研究进展 →','text-button');liveButton.onclick=showJourney;$('progress-strip').firstElementChild.append(liveButton);
 function apply(){document.documentElement.dataset.motion=prefs.motion?'on':'off';document.documentElement.dataset.reading=prefs.font;document.dispatchEvent(new Event('clink-preferences'));}
 function persist(){try{localStorage.setItem('clinkrag-preferences',JSON.stringify(prefs));$('settings-saved').textContent='已保存';}catch{$('settings-saved').textContent='无法保存到浏览器';}apply();}
 function applyDefaults(){if($('question').value.trim())return;runOptions.restore();$('method').value=prefs.method;$('initial-papers').value=String(prefs.initial);$('max-tokens').value=String(prefs.tokens);}
 function open(key,changingRun=false){
  if(key==='research'&&!run?.id){open('home');return;}
  screen=key;document.body.dataset.screen=key;
  for(const [id]of routes){const page=$(id+'-screen');if(page)page.hidden=id!==key;const b=$('sidebar').querySelector(`[data-screen="${id}"]`);if(b){b.classList.toggle('active',id===key);if(id===key)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');}}
  document.querySelector('.breadcrumb b').textContent=routes.find(r=>r[0]===key)?.[2]||'研究';document.body.classList.remove('sidebar-open');$('mobile-menu').setAttribute('aria-expanded','false');
  if(key==='library'){syncLibraryOptions();loadLibrary($('library-run').value);}
  if(key==='settings')renderSettings();
  if(key==='home'){$('home-question').value=$('question').value;syncHomeInput();syncHomeOptions();}
  if(key==='records')renderRecords();
  if(key==='experiments'){$('experiments-screen').append($('compare-view'));$('compare-tab').click();}
  else if($('compare-view').parentElement===$('experiments-screen')){$('trace-view').after($('compare-view'));switchTab(true);}
  if(key!=='research')window.paperGraph?.hide();
  if(key==='research'&&!changingRun&&document.body.dataset.view==='graph')$('graph-tab').click();
  window.scrollTo({top:0});
 }
 function renderHistory(items){records=items;renderRecords();if(libraryRun&&!items.some(r=>r.id===libraryRun)){libraryTicket++;libraryRun=null;library=null;$('library-list').replaceChildren();}if(screen==='library'){syncLibraryOptions();loadLibrary($('library-run').value);}}
 function recordCard(item){const card=create('button',undefined,'research-card');card.append(create('span',methodNames[item.method]||'科学文献研究','card-kicker'),create('h3',item.question||'未命名研究'));const meta=create('div',undefined,'record-meta');meta.append(create('span',statusNames[item.status]||item.status,'badge '+item.status),create('time',new Date(item.created_at).toLocaleDateString('zh-CN')),create('span',item.status==='running'?'查看进展 →':'打开研究 →'));card.append(meta);card.onclick=()=>loadRun(item.id).then(()=>{if(run.status==='running')showJourney();});return card;}
 function renderRecords(){const q=$('records-search').value.toLowerCase(),status=$('records-status').value,box=$('records-list');box.replaceChildren();const found=records.filter(r=>(r.question||'').toLowerCase().includes(q)&&(!status||r.status===status));found.forEach(r=>box.append(recordCard(r)));if(!found.length)box.append(create('p','没有符合筛选条件的研究。','empty'));}
 function syncLibraryOptions(){const select=$('library-run'),chosen=select.value||libraryRun||run?.id;select.replaceChildren();for(const r of records)select.append(new Option(r.question||r.id,r.id));if(records.some(r=>r.id===chosen))select.value=chosen;}
 async function loadLibrary(id){if(!id){$('library-list').textContent='还没有可查看的研究记录。';return;}if(id===libraryRun&&library){renderLibrary();return;}const ticket=++libraryTicket;libraryRun=id;library=null;libraryPage=0;$('library-list').textContent='正在读取已记录论文…';try{const value=await api(`/api/runs/${id}/graph`);if(ticket!==libraryTicket)return;library=value;renderLibrary();}catch(e){if(ticket===libraryTicket)$('library-list').textContent=e.message;}}
 function renderLibrary(){if(!library)return;const q=$('library-search').value.trim().toLowerCase(),scope=$('library-scope').value;let found=library.nodes.filter(n=>n.title.toLowerCase().includes(q)&&(scope==='all'||n[scope]));found.sort($('library-sort').value==='title'?(a,b)=>a.title.localeCompare(b.title):(a,b)=>Number(b.cited)-Number(a.cited)||Number(b.context)-Number(a.context)||a.title.localeCompare(b.title));const pages=Math.max(1,Math.ceil(found.length/15));libraryPage=Math.min(libraryPage,pages-1);$('library-count').textContent=`${found.length} / ${library.nodes.length} 篇`;$('library-page').textContent=`第 ${libraryPage+1} / ${pages} 页`;$('library-prev').disabled=libraryPage===0;$('library-next').disabled=libraryPage>=pages-1;const box=$('library-list');box.replaceChildren();
  for(const n of found.slice(libraryPage*15,(libraryPage+1)*15)){const row=create('article',undefined,'library-paper'),content=create('div');content.append(create('span',n.cited?'答案实际引用':n.context?'回答证据':n.retrieved?'已找到':'仅记录候选','card-kicker'),create('h3',n.title),create('p',`${n.passages.length} 个已记录文本窗口`,'fine'));const actions=create('div',undefined,'library-actions'),read=create('button','阅读原文','secondary'),map=create('button','探索关联 →','text-button');read.onclick=()=>readPaper(n);map.onclick=async()=>{if(run?.id!==libraryRun)await loadRun(libraryRun);else open('research');window.paperGraph.focus(n.id);};actions.append(read,map);row.append(content,actions);box.append(row);}if(!found.length)box.append(create('p','没有匹配论文，请调整标题关键词或状态筛选。','empty'));
 }
 function readPaper(n){const box=$('evidence-body');box.replaceChildren();const title=create('h2',n.title);title.id='evidence-title';box.append(create('span','文献库 · 已记录原文','section-kicker'),title);for(const [i,p]of n.passages.entries())box.append(create('h3',`文本窗口 ${i+1}`),create('p',p.text||'该记录没有保存原文。','original-text'));if(!n.passages.length)box.append(create('p','该记录没有保存原文。'));$('evidence-drawer').showModal();$('evidence-drawer').scrollTop=0;$('close-evidence').focus();}
 function renderSettings(){window.modelSettings?.entered();prefs.theme=document.documentElement.dataset.theme;for(const [id,key]of [['theme','theme'],['font','font'],['graph','graphLimit'],['method','method'],['initial','initial'],['tokens','tokens']])$('pref-'+id).value=String(prefs[key]);$('pref-motion').checked=prefs.motion;const box=$('settings-service');box.replaceChildren();for(const [label,value]of [['服务连接',connected?'已连接':'未连接'],['模型',config.model||'未配置'],['重排设备',config.device||'未配置'],['模型 API',config.llm_configured?'已配置':'未配置'],['检索 API',config.s2_configured?'已配置':'未配置']])box.append(create('dt',label),create('dd',value));}
 function showJourney(){window.paperGraph?.hide();for(const id of ['answer-view','trace-view','graph-view','compare-view'])$(id).hidden=true;for(const tab of document.querySelectorAll('.work-tabs [role=tab]')){const chosen=tab.id==='journey-tab';tab.classList.toggle('active',chosen);tab.setAttribute('aria-selected',String(chosen));}journey.hidden=false;document.body.dataset.view='journey';story.update(snapshot);story.render();}
 function hideJourney(){journey.hidden=true;$('journey-tab').classList.remove('active');$('journey-tab').setAttribute('aria-selected','false');}
 function update(state){const previousStatus=snapshot.run?.status;snapshot=state;if(screen==='settings')renderSettings();const changed=lastRun!==state.run?.id;lastRun=state.run?.id;story.update(state);if((changed||!previousStatus)&&screen==='research'&&state.run?.status){if(state.run.status==='running')showJourney();else switchTab(true);}if(state.run?.status==='running'&&document.body.dataset.view==='answer'&&!state.result?.answer&&screen==='research')showJourney();}
 window.researchApp={open,update,history:renderHistory,hideJourney,applyDefaults,preferences:()=>({...prefs})};
 for(const id of ['records-search','records-status'])$(id).addEventListener('input',renderRecords);
 for(const id of ['library-search','library-scope','library-sort'])$(id).addEventListener('input',()=>{libraryPage=0;renderLibrary();});$('library-run').onchange=e=>loadLibrary(e.target.value);$('library-prev').onclick=()=>{libraryPage--;renderLibrary();};$('library-next').onclick=()=>{libraryPage++;renderLibrary();};
 for(const [id,key]of [['theme','theme'],['font','font'],['graph','graphLimit'],['method','method'],['initial','initial'],['tokens','tokens']])$('pref-'+id).onchange=e=>{prefs[key]=['graphLimit','initial','tokens'].includes(key)?Number(e.target.value):e.target.value;if(key==='theme'&&document.documentElement.dataset.theme!==prefs.theme)$('theme-toggle').click();persist();};$('pref-motion').onchange=e=>{prefs.motion=e.target.checked;persist();};
 $('settings-reset').onclick=()=>{prefs={...defaults,theme:'dark'};if(document.documentElement.dataset.theme!=='dark')$('theme-toggle').click();persist();renderSettings();};$('settings-check').onclick=()=>connect().then(renderSettings);
 $('records-new').onclick=()=>openComposer();
 function syncHomeInput(){const input=$('home-question');updateControls();input.style.height='auto';input.style.height=Math.max(76,Math.min(240,input.scrollHeight))+'px';}
 $('home-question').value=$('question').value;
 $('home-question').oninput=()=>{$('question').value=$('home-question').value;saveDraft(true);syncHomeInput();};
 const customDialog=create('dialog');customDialog.id='custom-research-value';customDialog.setAttribute('aria-labelledby','custom-value-title');
 customDialog.innerHTML=`<form id="custom-value-form"><header><h2 id="custom-value-title"></h2><button type="button" id="custom-value-close" class="icon-button" aria-label="关闭自定义设置">×</button></header><p id="custom-value-description"></p><label for="custom-value-input" id="custom-value-label"></label><div class="custom-number-field"><input id="custom-value-input" type="number" step="1" required aria-describedby="custom-value-description custom-value-range"><span id="custom-value-unit"></span></div><small id="custom-value-range"></small><footer><button id="custom-value-cancel" class="secondary" type="button">取消</button><button class="primary" type="submit">应用</button></footer></form>`;document.body.append(customDialog);
 const advancedNumbers={
  'dimension-sources':{label:'每个维度的来源目标',unit:'篇',min:1,max:3,description:'每个研究维度希望找到的论文数量。少于目标时，按补检索设置继续查找。'},
  'extra-queries':{label:'补检索组数上限',unit:'组',min:0,max:4,description:'初次检索后，最多增加多少组查询来补充来源。设为 0 时不补检索。'},
  'context-tokens':{label:'证据阅读预算',unit:'tokens',min:1500,max:16000,description:'生成回答时，分配给原文片段与证据说明的输入预算。'},
  'initial-papers':{label:'初始证据起点数',unit:'个',min:1,max:8,description:'先选择多少个相关原文片段作为关系探索的起点。'},
  'graph-hops':{label:'关系扩展轮数',unit:'轮',min:0,max:3,description:'从初始证据出发，沿关系继续查找的轮数。设为 0 时只使用直接召回。'},
  'max-path':{label:'解释路径长度上限',unit:'段',min:1,max:4,description:'一条解释路径最多包含多少段关系。'},
  'max-tokens':{label:'模型输出上限',unit:'tokens',min:500,max:12000,description:'模型单次生成回答可使用的最大输出额度。'}
 };
 let customTarget='';
 for(const [id,setting]of Object.entries(advancedNumbers)){
  const control=$(id);control.dataset.committedValue=control.value;
  control.add(new Option('自定义…','custom'));
  const hint=create('small',`可自定义 ${setting.min.toLocaleString()}–${setting.max.toLocaleString()} ${setting.unit}`,'numeric-range-hint');hint.id=id+'-range';control.after(hint);control.setAttribute('aria-describedby',hint.id);
 }
 // Restore the committed value before form-level draft saving handles this change.
 $('run-form').addEventListener('change',event=>{
  const control=event.target;if(!advancedNumbers[control.id]||control.value!=='custom')return;
  control.value=control.dataset.committedValue;openCustomValue(control.id);
 },true);
 function syncHomeOptions(){
  $('method').value='clinkrag_online';
  const papers=$('online-papers').value,words=$('answer-words').value;
  $('home-range').replaceChildren(...[...new Set(['6','12','20','30',papers])].sort((a,b)=>Number(a)-Number(b)).map(v=>new Option(`最多分析 ${v} 篇论文`,v)),new Option('自定义篇数…','custom'));$('home-range').value=papers;
  $('home-length').replaceChildren(...[...new Set(['0','600','1200','2500','4000','6000',words])].sort((a,b)=>Number(a)-Number(b)).map(v=>new Option(Number(v)?`正文 · 约 ${Number(v).toLocaleString()} 字`:'正文长度 · 自动',v)),new Option('自定义字数…','custom'));$('home-length').value=words;
 }
 function applyHomeValue(target,value){
  setResearchSelect(target,value);
  if(target==='answer-words'&&Number(value)>0){const limit=[1800,3000,6000,10000,12000].find(n=>n>=Number(value)*2)||12000;if(limit>Number($('max-tokens').value))$('max-tokens').value=String(limit);}
  $(target).dispatchEvent(new Event('change',{bubbles:true}));syncHomeOptions();
 }
 function openCustomValue(target){
  customTarget=target;const setting=advancedNumbers[target]||(target==='online-papers'
   ?{label:'分析篇数',unit:'篇论文',min:3,max:30,description:'从检索结果中筛选论文，进入内容分析与关系构建。这里设置最多分析多少篇。'}
   :{label:'正文长度',unit:'字',min:1,max:6000,description:'设置回答正文的目标字数，模型会据此安排内容详略。'});
  $('custom-value-title').textContent='自定义'+setting.label;
  $('custom-value-description').textContent=setting.description;
  $('custom-value-label').textContent=setting.label;$('custom-value-unit').textContent=setting.unit;
  const input=$('custom-value-input');input.min=String(setting.min);input.max=String(setting.max);input.value=target==='answer-words'&&$(target).value==='0'?'1200':$(target).value;
  $('custom-value-range').textContent=`可设 ${setting.min.toLocaleString()}–${setting.max.toLocaleString()} ${setting.unit} · 整数`;
  syncHomeOptions();customDialog.showModal();input.focus();input.select();
 }
 $('custom-value-form').onsubmit=e=>{e.preventDefault();const input=$('custom-value-input');if(!input.reportValidity())return;applyHomeValue(customTarget,Number(input.value));customDialog.close();};
 $('custom-value-close').onclick=$('custom-value-cancel').onclick=()=>customDialog.close();
 customDialog.addEventListener('close',()=>{$(advancedNumbers[customTarget]?customTarget:customTarget==='online-papers'?'home-range':'home-length').focus();});
 $('home-range').onchange=()=>{$('home-range').value==='custom'?openCustomValue('online-papers'):applyHomeValue('online-papers',$('home-range').value);};
 $('home-length').onchange=()=>{$('home-length').value==='custom'?openCustomValue('answer-words'):applyHomeValue('answer-words',$('home-length').value);};
 $('home-more').onclick=()=>{openComposer(false,true);showComposerPanel('retrieval');$('research-dialog').querySelector('[data-composer-section="retrieval"]').focus();};
 $('research-dialog').addEventListener('close',()=>{if(screen==='home'){$('home-question').value=$('question').value;syncHomeInput();syncHomeOptions();}});
 $('home-compose').onsubmit=e=>{e.preventDefault();if(window.modelSettings?.isBusy()){toast('模型正在保存，请稍候');return;}const q=$('home-question').value.trim();if(!q)return;$('question').value=q;saveDraft(true);$('run-form').requestSubmit();};
 if(!storageRead('clinkrag-draft'))applyDefaults();
 apply();open('home');
 // Hydrate even when a fast local response preceded this deferred script.
 if(run?.id)update({run,result,steps});
 history().then(renderHistory).catch(()=>{});
})();
