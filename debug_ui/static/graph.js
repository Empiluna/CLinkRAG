/* Paper-level projection of recorded evidence. No network libraries or inferred edges. */
(() => {
 const host=$('graph-view'), NS='http://www.w3.org/2000/svg';
 let data=null, active=false, phase='pool', picked=null, edgePicked=null, graphRun=null, requestId=0;
 let zoom=1, pan={x:0,y:0}, positions=new Map(), layoutKey='', visibleEdges=[], visibleNodes=[];
 const mapWidth=1040;let mapHeight=600;
 const titleMeasure=document.createElement('canvas').getContext('2d');
 if(titleMeasure)titleMeasure.font="16px 'Segoe UI','Microsoft YaHei',sans-serif";
 function titleLines(title){
  const width=text=>titleMeasure?titleMeasure.measureText(text).width:Array.from(text).length*16;
  const tokens=(title.match(/\s+|[A-Za-z0-9]+(?:['’\-][A-Za-z0-9]+)*|[^\s]/gu)||[]).flatMap(token=>width(token)>208?Array.from(token):[token]);
  const lines=[];let line='';
  for(const token of tokens){
   if(width(line+token)>208&&line){
    if(lines.length===2){line=line.trimEnd();while(line&&width(line+'…')>208)line=line.slice(0,-1);lines.push(line+'…');return lines;}
    lines.push(line.trim());line='';
   }
   if(line||token.trim())line+=token;
  }
  if(line.trim())lines.push(line.trim());return lines;
 }
 let motionFrame=0, finishMotion=null;
 let mode='overview', neighborhoodPage=0, directoryPage=0, detailOpen=false, exploration=null, centerHistory=[];
 const motionOff=()=>motionPreference.matches||document.documentElement.dataset.motion==='off';
 const motionPreference=matchMedia('(prefers-reduced-motion: reduce)');
 function stopMotion(){if(motionFrame)cancelAnimationFrame(motionFrame);motionFrame=0;if(finishMotion)finishMotion();finishMotion=null;delete host.dataset.layoutAnimating;}
 motionPreference.addEventListener('change',()=>{if(motionOff())stopMotion();});
 document.addEventListener('visibilitychange',()=>{if(document.hidden)stopMotion();});
 document.addEventListener('clink-preferences',()=>{stopMotion();if(active&&data)render();});
 const types={shared:'讨论同一概念',cooccurrence:'讨论相关概念',path:'解释可以衔接',citation:'论文引用'};
 const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
 const svg=(tag,attrs={})=>{const n=document.createElementNS(NS,tag);for(const [k,v] of Object.entries(attrs))n.setAttribute(k,v);return n;};
 const names=()=>data?.entity_labels||{};
 host.innerHTML=`<div class="graph-heading"><div><div class="section-kicker">QUESTION / EVIDENCE MAP</div><h2>论文如何相连</h2><p id="graph-summary" class="fine" role="status">选择一项运行记录后查看。</p></div><div class="graph-heading-actions"><button id="graph-fullscreen" class="secondary" aria-pressed="false">放大查看</button><button id="graph-refresh" class="secondary">刷新</button></div></div>
 <div id="graph-phases" class="graph-phases" aria-label="检索阶段"></div>
 <div class="explore-modes" role="group" aria-label="图谱探索方式"><button data-explore="overview">关系图</button><button data-explore="directory">全部论文</button></div><div id="graph-overview"></div><div id="graph-directory" hidden></div><div id="graph-local-bar" hidden></div>
 <details class="graph-filters"><summary>关系类型与连接筛选</summary><div class="graph-controls"><div id="graph-types" class="graph-types"></div><label>连接密度 <select id="graph-density"><option value="sparse">中心论文的直接连接</option></select></label><label>共同概念至少 <select id="graph-strength"><option value="1" selected>1 个</option><option value="2">2 个</option><option value="3">3 个</option></select></label></div>
 </details><div class="graph-tools"><input id="graph-search" type="search" placeholder="搜索论文标题" aria-label="查找论文标题"><select id="graph-paper-list" aria-label="选择论文查看详情"><option value="">选择论文查看详情…</option></select><button id="graph-clear" class="text-button">清除聚焦</button><button id="graph-reset" class="text-button">重置视图</button></div>
 <div class="graph-legend"><span class="seed">● 首先找到</span><span class="expanded">● 进一步找到</span><span class="used">● 回答证据</span><span>卡片标注：答案是否引用</span><span>灰色：找到的论文</span></div>
 <div class="graph-layout"><div class="graph-canvas-wrap"><svg id="paper-network" viewBox="0 0 1040 600" role="group" aria-label="交互论文关系图；可使用上方选择框和右侧关联列表访问所有节点与边"><defs><marker id="graph-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#9a79c0"/></marker></defs><g id="graph-viewport"><g id="graph-edges"></g><g id="graph-nodes"></g></g></svg><p id="graph-empty" hidden></p><div class="graph-zoom"><button id="graph-minus" aria-label="缩小">−</button><button id="graph-plus" aria-label="放大">＋</button></div><p class="graph-hint">拖动节点 / 空白处平移 · Ctrl + 滚轮缩放 · 点击连线查看依据</p></div><aside id="graph-inspector" aria-live="polite"></aside><button id="graph-close-inspector" class="icon-button" aria-label="关闭论文关系详情">×</button></div>
 <p id="graph-coverage" class="fine graph-footnote"></p><div class="graph-paths"><h3>从论文关联到解释路径</h3><p class="fine">上图展示论文关联，下方展示原文关系与接续路径。</p><div id="graph-path-list"></div></div>`;
 for(const b of host.querySelectorAll('[data-explore]'))b.onclick=()=>{mode=b.dataset.explore;detailOpen=false;render();};
 for(const [key,label] of Object.entries(types)){const l=el('label');const input=el('input');input.type='checkbox';input.value=key;input.checked=true;input.onchange=draw;l.append(input,el('span',label,'edge-key '+key));$('graph-types').append(l);}
 function hide(){stopMotion();document.body.classList.remove('graph-fullscreen');$('graph-fullscreen').setAttribute('aria-pressed','false');$('graph-fullscreen').textContent='放大查看';active=false;host.hidden=true;$('graph-tab').classList.remove('active');$('graph-tab').setAttribute('aria-selected','false');}
 function reset(){stopMotion();mapSeen.clear();mapDOMKey='';mapObserver?.disconnect();phase='pool';mode='overview';neighborhoodPage=0;directoryPage=0;detailOpen=false;$('graph-search').value='';centerHistory=[];requestId++;data=null;graphRun=null;picked=null;edgePicked=null;positions.clear();layoutKey='';$('graph-summary').textContent='正在等待本次检索记录…';$('graph-nodes').replaceChildren();$('graph-edges').replaceChildren();$('graph-path-list').replaceChildren();$('graph-overview').replaceChildren(el('p','正在载入论文关系…','empty'));$('graph-directory').replaceChildren();}
 async function refresh(){if(!active||!run?.id)return;const id=run.id, ticket=++requestId;try{const value=await api(`/api/runs/${id}/graph`);if(ticket!==requestId||run?.id!==id)return;data=value;graphRun=id;render();}catch(e){$('graph-summary').textContent='图谱加载失败：'+e.message;mapDOMKey='';$('graph-overview').replaceChildren(el('p','论文关系暂时未能载入，请点击刷新。','empty'));}}
 function show(){switchTab(false);$('trace-view').hidden=true;$('answer-view').hidden=true;$('compare-view').hidden=true;for(const id of ['trace-tab','answer-tab','compare-tab']){$(id).classList.remove('active');$(id).setAttribute('aria-selected','false');}active=true;document.body.dataset.view='graph';host.hidden=false;$('graph-tab').classList.add('active');$('graph-tab').setAttribute('aria-selected','true');if(data&&graphRun===run?.id)render();else refresh();}
 window.paperGraph={hide,reset,refresh,focus:id=>{centerHistory=[];phase='pool';mode='overview';picked=id;neighborhoodPage=0;detailOpen=false;show();},showPhase:key=>{phase='pool';mode='overview';picked=null;edgePicked=null;neighborhoodPage=0;show();}};$('graph-tab').onclick=show;$('graph-refresh').onclick=refresh;
 function render(){
  $('graph-summary').textContent=run?.question||'尚未选择问题';
  $('graph-phases').replaceChildren();
  for(const [key,label] of [['pool','全部找到的论文'],['seed','首先找到'],['retrieved','进一步查找'],['context','回答证据']]){
   const count=data.nodes.filter(n=>key==='pool'||n[key]).length;const b=el('button');b.type='button';b.className=phase===key?'active':'';b.setAttribute('aria-pressed',phase===key);b.append(el('small',label),el('strong',`${count} 篇`));b.onclick=()=>{phase=key;centerHistory=[];picked=null;edgePicked=null;neighborhoodPage=0;directoryPage=0;detailOpen=false;render();};$('graph-phases').append(b);
  }
  renderPaths();draw();
 }
 function explorerUI(){
  for(const b of host.querySelectorAll('[data-explore]')){b.classList.toggle('active',b.dataset.explore===mode);b.setAttribute('aria-pressed',String(b.dataset.explore===mode));}
  host.dataset.explore=mode;
  host.querySelector('.graph-tools').hidden=mode==='overview';
  host.querySelector('.graph-paths').hidden=mode!=='local';
  host.querySelector('[data-explore=directory]').textContent=`全部论文 · ${data.nodes.length}`;
  host.querySelector('.graph-tools').after($('graph-overview'),$('graph-directory'),$('graph-local-bar'));
  host.querySelector('.graph-layout').hidden=mode!=='local';host.querySelector('.graph-legend').hidden=mode!=='local';host.querySelector('.graph-filters').hidden=mode!=='local';$('graph-coverage').hidden=mode!=='local';
  $('graph-overview').hidden=mode!=='overview';$('graph-directory').hidden=mode!=='directory';$('graph-local-bar').hidden=mode!=='local';
  $('graph-paper-list').hidden=mode!=='local';$('graph-clear').hidden=mode!=='local';$('graph-reset').hidden=mode!=='local';
  const openPaper=n=>{centerHistory=[];mode='overview';picked=n.id;neighborhoodPage=0;detailOpen=false;edgePicked=null;draw();};
  const paperRow=n=>{const b=el('button',undefined,'explore-paper');b.append(el('span',String(data.nodes.findIndex(x=>x.id===n.id)+1).padStart(2,'0'),'paper-order'),el('strong',n.title),el('small',`${n.context?'回答证据 · ':''}${exploration.degree.get(n.id)||0} 条已记录的连接`),el('span','探索关联 →','paper-action'));b.onclick=()=>openPaper(n);return b;};
  if(mode==='overview')renderPaperMap();
  if(mode==='directory'){
   const box=$('graph-directory'),query=$('graph-search').value.trim().toLowerCase(),papers=exploration.ranked.filter(n=>n.title.toLowerCase().includes(query));
   const pages=Math.max(1,Math.ceil(papers.length/12));directoryPage=Math.min(directoryPage,pages-1);box.replaceChildren(el('p',`${papers.length} 篇匹配论文 · 第 ${directoryPage+1} / ${pages} 页`,'directory-count'));
   papers.slice(directoryPage*12,(directoryPage+1)*12).forEach(n=>box.append(paperRow(n)));if(!papers.length)box.append(el('p','没有匹配标题，试试更短的关键词或切换阶段。','empty'));
   const pager=el('div',undefined,'directory-pager');for(const [label,direction]of [['上一页',-1],['下一页',1]]){const b=el('button',label,'secondary');b.disabled=direction<0?directoryPage===0:directoryPage>=pages-1;b.onclick=()=>{directoryPage+=direction;draw();};pager.append(b);}box.append(pager);
  }
  if(mode==='local'){
   const box=$('graph-local-bar');box.replaceChildren();const caption=el('div');caption.append(el('strong','以这篇论文为中心'),el('p',exploration.center?.title||'当前没有论文','fine'),el('span',exploration.neighbors.length?`共 ${exploration.neighbors.length} 篇直接关联 · 第 ${exploration.page+1} / ${exploration.pages} 组`:'没有记录符合筛选条件的直接关系，可查看原文或在目录中换一篇论文。','fine'));box.append(caption);
   const actions=el('div',undefined,'local-actions');const back=el('button','返回上一中心','secondary');back.disabled=!centerHistory.length;back.onclick=()=>{const prev=centerHistory.pop();if(prev){picked=prev.id;neighborhoodPage=prev.page;edgePicked=null;detailOpen=false;draw();}};actions.append(back);for(const [label,direction]of [['上一组',-1],['下一组',1]]){const b=el('button',label,'secondary');b.disabled=direction<0?exploration.page===0:exploration.page>=exploration.pages-1;b.onclick=()=>{neighborhoodPage+=direction;draw();};actions.append(b);}const detail=el('button','查看中心论文证据','secondary');detail.disabled=!exploration.center;detail.onclick=()=>{detailOpen=true;edgePicked=null;draw();};actions.append(detail);box.append(actions);
   let mobile=$('mobile-relations');if(!mobile){mobile=el('div',undefined,'mobile-relations');mobile.id='mobile-relations';host.querySelector('.graph-canvas-wrap').append(mobile);}mobile.replaceChildren();
   for(const n of exploration.nodes.slice(1)){const card=el('div',undefined,'mobile-relation'),relations=exploration.links.filter(e=>e.source===n.id||e.target===n.id);const descriptions=[...new Set(relations.map(e=>e.type==='citation'?(e.source===n.id?'此论文 → 引用中心论文':'中心论文 → 引用此论文'):e.type==='path'?(e.source===n.id?'此论文 → 候选证据接续 → 中心论文':'中心论文 → 候选证据接续 → 此论文'):types[e.type]))];card.append(el('span',descriptions.join(' · '),'mobile-edge-label'));const title=el('button',n.title,'mobile-paper-link');title.onclick=()=>selectNode(n.id);const evidence=el('button','核对这条关系 →','text-button');evidence.onclick=()=>selectEdge(relations[0]);card.append(title,evidence);mobile.append(card);}if(!exploration.neighbors.length)mobile.append(el('p','没有已记录的直接关联。','fine'));
  }
 }
 let mapDOMKey='',mapObserver=null;const mapSeen=new Set();
 const mapNavigation=el('div',undefined,'map-navigation');host.querySelector('.explore-modes').before(mapNavigation);mapNavigation.append(host.querySelector('.explore-modes'));
 const mapDialog=el('dialog',undefined,'paper-map-dialog');mapDialog.setAttribute('aria-label','论文与连接依据');
 const mapClose=el('button','×','map-dialog-close');mapClose.setAttribute('aria-label','关闭详情');mapClose.onclick=()=>mapDialog.close();
 const mapDetail=el('div');mapDialog.append(mapClose,mapDetail);host.append(mapDialog);
 mapDialog.onclick=e=>{if(e.target===mapDialog)mapDialog.close();};
 function showMapDetail(title){mapDetail.replaceChildren(el('h2',title));if(!mapDialog.open)mapDialog.showModal();mapDialog.scrollTop=0;}
 function mapPaperDetails(n){
  showMapDetail(n.title);
  const focus=el('button','查看这篇论文的关系','secondary');focus.onclick=()=>{mapDialog.close();picked=n.id;neighborhoodPage=0;draw();};mapDetail.append(focus);
  const url=n.url||(/^[a-f0-9]{40}$/i.test(n.id)?'https://www.semanticscholar.org/paper/'+n.id:null);
  if(url&&/^https?:\/\//i.test(url)){const a=el('a','打开论文原网页 ↗');a.href=url;a.target='_blank';a.rel='noopener noreferrer';mapDetail.append(a);}
  mapDetail.append(el('h3','本次阅读的原文'));
  const passages=[...new Set((n.passages||[]).map(p=>p.text).filter(Boolean))];
  if(!passages.length)mapDetail.append(el('p','这篇论文暂时只有标题记录。'));
  for(const text of passages)mapDetail.append(el('p',text,'map-original'));
 }
 function mapEdgeDetails(edges,left,right){
  showMapDetail('这两篇论文为什么相连？');
  for(const n of [left,right]){const b=el('button',n.title,'map-detail-paper');b.onclick=()=>mapPaperDetails(n);mapDetail.append(b);}
  for(const e of edges){
   mapDetail.append(el('h3',types[e.type]));
   if(e.type==='shared')for(const item of e.evidence||[]){
    mapDetail.append(el('strong',item.entity));
    for(const n of [left,right]){
     const mentions=(item.mentions||[]).filter(m=>m.paper_id===n.id);
     const texts=[...new Set(mentions.map(m=>n.passages?.find(p=>p.id===m.passage_id)?.text||m.mention).filter(Boolean))];
     mapDetail.append(el('h4',n.title));for(const text of texts)mapDetail.append(el('p',text,'map-original'));
    }
   }
   else if(e.type==='cooccurrence')for(const item of e.evidence||[])mapDetail.append(el('p',`${item.source_entity} ↔ ${item.target_entity}：在 ${item.papers} 篇论文、${item.windows} 个原文片段中一起出现。`));
   else if(e.type==='path'){mapDetail.append(el('p',e.selected?'这段解释已用于回答。':'这是一条待核对的解释线索。'));for(const c of e.evidence||[])mapDetail.append(el('p',c.quote||'','map-original'));}
   else mapDetail.append(el('p',`${e.source===left.id?left.title:right.title} 引用了 ${e.target===right.id?right.title:left.title}。`));
  }
 }
 function mapReason(edges,center){
  const shared=edges.filter(e=>e.type==='shared').flatMap(e=>e.evidence||[]).map(e=>e.entity);
  if(shared.length)return ['都提到了', [...new Set(shared)].join(' / ')];
  const citation=edges.find(e=>e.type==='citation');if(citation)return [citation.source===center.id?'左侧论文引用了':'右侧论文引用了','点击查看引用方向'];
  const path=edges.find(e=>e.type==='path');if(path)return [path.selected?'回答使用的解释链':'可衔接的解释线索','点击查看原文'];
  const item=edges.find(e=>e.type==='cooccurrence')?.evidence?.[0];
  return ['讨论相关概念',item?`${item.source_entity} / ${item.target_entity}`:'点击查看依据'];
 }
 function renderPaperMap(){
  const box=$('graph-overview'),ex=exploration,center=ex.center,leaves=ex.nodes.slice(1);
  const key=JSON.stringify([graphRun,phase,center?.id,ex.page,ex.nodes.map(n=>[n.id,n.title,n.cited,n.passages?.length]),ex.links,ex.scope.length]);
  if(mapDOMKey===key&&box.childElementCount)return;
  mapObserver?.disconnect();mapDOMKey=key;box.replaceChildren();
  mapNavigation.querySelector('.paper-map-toolbar')?.remove();const toolbar=el('div',undefined,'paper-map-toolbar');
  const label=el('label','查看论文');const select=el('select');select.setAttribute('aria-label','选择图中的中心论文');
  for(const n of ex.ranked)select.append(new Option(n.title,n.id));select.value=center?.id||'';
  select.onchange=()=>{picked=select.value;neighborhoodPage=0;draw();};label.append(select);toolbar.append(label);
  mapNavigation.append(toolbar);
  if(!center){box.append(el('p','找到论文后，关系图会在这里逐步出现。','empty'));return;}
  const card=(n,central=false)=>{
   const b=el('button',undefined,'map-paper'+(central?' map-center':' map-leaf'));b.type='button';
   b.append(el('span',central?'当前论文':n.cited?'已用于回答':'相关论文','map-paper-tag'),el('strong',n.title),el('span',[n.year,n.cited?'已用于回答':'', '查看原文 ↗'].filter(Boolean).join(' · '),'map-paper-meta'));
   b.onclick=()=>mapPaperDetails(n);return b;
  };
  const surface=el('div',undefined,'paper-map-surface');box.append(surface);
  if(!leaves.length){
   surface.classList.add('map-unlinked');surface.append(card(center,true),el('p','这篇论文暂时没有已记录的跨篇连接。可以换一篇查看。','map-unlinked-note'));
  }else{
   const network=svg('svg',{'class':'map-connectors','aria-hidden':'true',preserveAspectRatio:'none'});surface.append(network);
   const origin=card(center,true);origin.style.gridRow=`1 / span ${leaves.length}`;surface.append(origin);
   const targets=[],arrivals=[];
   leaves.forEach((n,i)=>{
    const edges=ex.links.filter(e=>e.source===n.id||e.target===n.id),[label,topic]=mapReason(edges,center);
    const reason=el('button',undefined,'map-reason');reason.type='button';reason.style.gridRow=i+1;reason.style.gridColumn=2;
    reason.append(el('span',label),el('strong',topic),el('small','查看连接依据'));reason.onclick=()=>mapEdgeDetails(edges,center,n);
    const seenKey=JSON.stringify([center.id,n.id,edges.map(e=>[e.type,e.source,e.target,e.evidence])]);
    const fresh=!motionOff()&&!mapSeen.has(seenKey);mapSeen.add(seenKey);arrivals.push(fresh);
    const target=card(n);target.style.gridRow=i+1;target.style.gridColumn=3;target.style.setProperty('--arrival-delay',`${350+i*100}ms`);
    if(fresh)target.classList.add('map-arrival');
    surface.append(reason,target);targets.push(target);
   });
   let lastSize='',firstDraw=true;
   const connect=()=>{
    if(!surface.isConnected||surface.getBoundingClientRect().width===0)return;
    const area=surface.getBoundingClientRect(),a=origin.getBoundingClientRect(),rects=targets.map(t=>t.getBoundingClientRect());
    const size=JSON.stringify([area.width,area.height,a.x,a.y,...rects.map(r=>[r.x,r.y,r.height])]);if(size===lastSize)return;lastSize=size;
    network.setAttribute('viewBox',`0 0 ${area.width} ${area.height}`);network.replaceChildren();
    rects.forEach((b,i)=>{
     const narrow=matchMedia('(max-width:700px)').matches;
     const x1=narrow?a.x+a.width/2-area.x:a.right-area.x,y1=narrow?a.bottom-area.y:a.y+a.height/2-area.y;
     const x2=b.x-area.x,y2=b.y+b.height/2-area.y;
     const middle=(x1+x2)/2;
     const d=narrow?`M ${x1} ${y1} L ${x1} ${y1+12} L 10 ${y1+12} L 10 ${y2} L ${x2} ${y2}`:`M ${x1} ${y1} C ${x1+50} ${y1}, ${middle-60} ${y2}, ${middle} ${y2} L ${x2} ${y2}`;
     const track=svg('path',{d,'class':'map-link-track'}),line=svg('path',{d,pathLength:1,'class':'map-link-draw'+(firstDraw&&arrivals[i]?' map-drawing':'')});line.style.animationDelay=`${i*100}ms`;network.append(track,line);
    });
    firstDraw=false;
   };
   mapObserver=new ResizeObserver(connect);mapObserver.observe(surface);targets.forEach(t=>mapObserver.observe(t));requestAnimationFrame(connect);
  }
  const footer=el('div',undefined,'paper-map-footer');
  footer.append(el('span',leaves.length?`这篇论文连接了 ${ex.neighbors.length} 篇 · 正在显示 ${ex.page*3+1}–${ex.page*3+leaves.length} 篇`:'所有论文都可在“全部论文”中找到'));
  footer.append(el('span',`共 ${ex.edges.length} 条已记录关系`,'paper-map-total'));
  if(ex.pages>1){const controls=el('div');for(const [text,delta] of [['上一组',-1],['下一组',1]]){const b=el('button',text,'secondary');b.disabled=delta<0?ex.page===0:ex.page===ex.pages-1;b.onclick=()=>{neighborhoodPage+=delta;draw();};controls.append(b);}footer.append(controls);}box.append(footer);
 }
 function layout(nodes){
  const key=nodes.map(n=>n.id).join('|');if(key===layoutKey)return;layoutKey=key;
  const leaf=nodes.length-1,perSide=Math.ceil(leaf/2);
  mapHeight=Math.max(600,perSide*124+40);host.style.setProperty('--map-height',mapHeight+'px');
  $('paper-network').setAttribute('viewBox',`0 0 ${mapWidth} ${mapHeight}`);
  positions=new Map(nodes.map((n,i)=>{if(!i)return[n.id,{x:mapWidth/2,y:mapHeight/2}];const slot=(i-1)%Math.max(1,perSide),right=i-1>=perSide;return[n.id,{x:right?890:150,y:perSide===1?mapHeight/2:76+slot*((mapHeight-152)/(perSide-1))}];}));
  zoom=1;pan={x:0,y:0};
 }
 function draw(){
  if(!data)return;
  stopMotion();const previous=new Map([...positions].map(([id,p])=>[id,{...p}])),previousKey=layoutKey;
  const allowed=new Set([...$('graph-types').querySelectorAll('input:checked')].map(x=>x.value));
  const limit=mode==='overview'?4:(window.researchApp?.preferences().graphLimit||10);
  exploration=paperExplorer.select(data,{phase,anchor:picked,limit,page:neighborhoodPage,types:allowed,min:Number($('graph-strength').value)});
  neighborhoodPage=exploration.page;visibleNodes=mode==='local'?exploration.nodes:[];visibleEdges=mode==='local'?exploration.links:[];
  explorerUI();
  if(mode!=='local'){$('graph-nodes').replaceChildren();$('graph-edges').replaceChildren();layoutKey='';host.classList.remove('inspecting');return;}
  picked=exploration.center?.id||null;const ids=new Set(visibleNodes.map(n=>n.id)),opening=detailOpen&&!host.classList.contains('inspecting');host.classList.toggle('inspecting',detailOpen);
  if(picked&&!ids.has(picked))picked=null;
  const term=$('graph-search').value.trim().toLowerCase();
  const neighbor=new Set(picked?[picked,...visibleEdges.filter(e=>e.source===picked||e.target===picked).flatMap(e=>[e.source,e.target])]:[]);
  layout(visibleNodes);$('graph-edges').replaceChildren();$('graph-nodes').replaceChildren();
  for(const e of visibleEdges){const a=positions.get(e.source),b=positions.get(e.target);const g=svg('g',{'class':`graph-edge ${e.type}${(picked&&e.source!==picked&&e.target!==picked)||(edgePicked&&edgePicked!==e.id)?' dim':''}${edgePicked===e.id?' chosen':''}`,'data-edge':e.id});
   const attrs=edgeCoordinates(a,b);const line=svg('line',attrs);if(e.directed)line.setAttribute('marker-end','url(#graph-arrow)');
   const hit=svg('line',{...attrs,'class':'edge-hit'});const title=svg('title');title.textContent=e.label;g.append(line,hit,title);g.onclick=()=>selectEdge(e);$('graph-edges').append(g);
  }
  for(const [i,n] of visibleNodes.entries()){
   const p=positions.get(n.id),color=n.context?'used':n.seed?'seed':n.retrieved?'expanded':'pool';
   const selectedEdge=edgePicked?visibleEdges.find(e=>e.id===edgePicked):null;
   const dim=(picked&&!neighbor.has(n.id))||(selectedEdge&&![selectedEdge.source,selectedEdge.target].includes(n.id))||(term&&!n.title.toLowerCase().includes(term));
   const g=svg('g',{'class':`paper-node ${color}${dim?' dim':''}${picked===n.id?' selected':''}`,'transform':`translate(${p.x},${p.y})`,'data-paper':n.id,'tabindex':'0','role':'button','aria-label':n.title});
   g.append(svg('rect',{x:-120,y:-52,width:240,height:104,rx:12,'class':'paper-card'}));
   const num=svg('text',{'text-anchor':'start',x:-104,y:-31,'class':'node-number'});num.textContent=String(data.nodes.findIndex(p=>p.id===n.id)+1).padStart(2,'0')+'  ·  '+(n.cited?'回答已引用':n.context?'回答证据':n.seed?'首先找到':'关联论文');
   const title=svg('title');title.textContent=n.title;
   const label=svg('text',{'text-anchor':'start',x:-104,y:-8,'class':'node-label'});
   for(const [j,text] of titleLines(n.title).entries()){const line=svg('tspan',{x:-104,dy:j?21:0});line.textContent=text;label.append(line);}
   g.append(num,title,label);g.onclick=()=>{if(!dragMoved)selectNode(n.id);};g.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();selectNode(n.id);}};
   $('graph-nodes').append(g);
  }
  $('graph-paper-list').replaceChildren(new Option('选择论文查看详情…',''));exploration.ranked.forEach(n=>$('graph-paper-list').append(new Option(n.title,n.id)));$('graph-paper-list').value=picked||'';
  $('graph-empty').hidden=!!visibleNodes.length;$('graph-empty').textContent=phase==='seed'?'这次记录尚未提供可识别的首先找到论文。':'当前阶段尚无论文记录。任务进行中时会自动更新。';
  const total=exploration.edges.length;
  $('graph-coverage').textContent=`本阶段 ${exploration.scope.length} 篇论文；当前展开 ${visibleNodes.length} 篇、${visibleEdges.length} 条直接关系。中心论文共有 ${exploration.neighbors.length} 篇关联，可翻页查看。其余论文保留在目录中。`;
  if(!picked&&!edgePicked)welcome();else if(picked)paperDetail(data.nodes.find(n=>n.id===picked));
  transform();
  if(previousKey!==layoutKey)animateLayout(previous);if(opening&&matchMedia('(max-width:760px)').matches)requestAnimationFrame(()=>$('graph-inspector').scrollIntoView({block:'start',behavior:motionOff()?'instant':'smooth'}));
 }
 function edgeCoordinates(a,b){const dx=b.x-a.x,dy=b.y-a.y,d=Math.hypot(dx,dy)||1,ux=dx/d,uy=dy/d,o=Math.min(125/Math.max(.001,Math.abs(ux)),57/Math.max(.001,Math.abs(uy)),d*.45);return{x1:a.x+ux*o,y1:a.y+uy*o,x2:b.x-ux*o,y2:b.y-uy*o};}
 function animateLayout(previous){
  if(motionOff()||document.hidden||visibleNodes.length>80)return;
  host.dataset.layoutAnimating='true';
  const nodes=[...$('graph-nodes').children].map(g=>{const id=g.dataset.paper,to=positions.get(id);return{g,id,to,from:previous.get(id)||{x:mapWidth/2+(to.x-mapWidth/2)*.72,y:mapHeight/2+(to.y-mapHeight/2)*.72},fresh:!previous.has(id)};});
  const edges=[...$('graph-edges').children].map((g,i)=>({lines:[...g.querySelectorAll('line')],edge:visibleEdges[i]}));
  const start=performance.now();
  const frame=t=>{
   const progress=Math.min(1,(t-start)/680),ease=1-Math.pow(1-progress,4),current=new Map();
   for(const n of nodes){const p={x:n.from.x+(n.to.x-n.from.x)*ease,y:n.from.y+(n.to.y-n.from.y)*ease};current.set(n.id,p);n.g.setAttribute('transform',`translate(${p.x},${p.y})`);if(n.fresh)n.g.style.opacity=String((n.g.classList.contains('dim')?.18:1)*Math.min(1,progress*2.5));}
   for(const {lines,edge} of edges){const a=current.get(edge.source),b=current.get(edge.target);for(const line of lines)for(const [k,v]of Object.entries(edgeCoordinates(a,b)))line.setAttribute(k,v);}
   if(progress<1)motionFrame=requestAnimationFrame(frame);else{nodes.forEach(n=>n.g.style.removeProperty('opacity'));motionFrame=0;finishMotion=null;delete host.dataset.layoutAnimating;}
  };
  finishMotion=()=>frame(start+680);frame(start);
 }
 function welcome(){const box=$('graph-inspector');box.replaceChildren(el('div','READ THE CONNECTIONS','section-kicker'),el('h3','先选一篇论文，再看它与谁相连'),el('p','点击节点查看进入检索的原因和证据原文；点击连线核对共同实体、共现统计或跨篇接续。','graph-description'),el('p','蓝色表示首先找到，紫色表示进一步找到，绿色表示进入回答上下文。双圈表示答案实际使用了该论文的引用编号。','fine'));}
 function selectNode(id){if(picked&&picked!==id)centerHistory.push({id:picked,page:neighborhoodPage});picked=id;edgePicked=null;mode='local';neighborhoodPage=0;detailOpen=false;draw();const target=[...$('graph-nodes').children].find(g=>g.dataset.paper===id);target?.focus({preventScroll:true});if(matchMedia('(max-width:760px)').matches)$('graph-local-bar').scrollIntoView({block:'start',behavior:motionOff()?'instant':'smooth'});}
 function paperDetail(n){if(!n)return;const box=$('graph-inspector');box.replaceChildren(el('div','PAPER / RETRIEVAL EVIDENCE','section-kicker'),el('h3',n.title));
  const tags=[n.seed?'首先找到':null,n.retrieved?'已选中':null,n.context?'回答证据':null,n.cited?'答案已引用':null].filter(Boolean);box.append(el('p',tags.join(' · ')||'找到的论文','graph-status'));
  if(typeof n.indexed==='boolean')box.append(el('p',n.indexed?'已纳入本次摘要建图':`未纳入建图：${n.exclusion_reason||'尚在筛选中'}`,'fine'));
  if(n.score!=null)box.append(el('p',`相关程度得分：${Number(n.score).toFixed(3)}（不是置信概率）`,'fine'));
  if(/^[a-f0-9]{40}$/i.test(n.id)){const a=el('a','打开论文 ↗');a.href='https://www.semanticscholar.org/paper/'+n.id;a.target='_blank';a.rel='noopener noreferrer';box.append(a);}
  const links=visibleEdges.filter(e=>e.source===n.id||e.target===n.id);box.append(el('h4',`关联论文 · ${links.length} 条当前可见连接`));
  for(const edge of links){const other=data.nodes.find(x=>x.id===(edge.source===n.id?edge.target:edge.source));const b=el('button',`${edge.label} · ${other.title}`,'graph-related');b.onclick=()=>selectEdge(edge);box.append(b);}
  box.append(el('h4',`原始证据 · ${n.passages.length} 个已记录窗口`));
  for(const p of n.passages){const d=el('details'),s=el('summary',p.retrieved?'已选中的片段 · 查看原文与原因':'其他片段 · 查看原文');d.append(s,el('p',p.text||'本次记录未提供原文。','graph-quote'));const reasons=p.reasons||[];
   for(const r of reasons){const labels=names();let text=r.type==='coverage_seed'?'按维度定位与来源多样性直接召回':r.type==='semantic_seed'?'语义相关性召回':r.type==='shared_entity'?`共同概念：${labels[r.entity]||r.entity}`:r.type==='recorded_retrieval'?'来自已记录检索输出':r.type==='api_candidate'?'API 返回候选，未记录进入后续检索步骤':`${r.type==='co_occurs'?'概念关联':'关系扩展'}：${labels[r.source]||r.source} ↔ ${labels[r.target]||r.target}`;if(r.hop)text+=` · 第 ${r.hop} 跳`;d.append(el('p',text,'fine'));}box.append(d);
  }
 }
 function selectEdge(e){edgePicked=e.id;detailOpen=true;draw();const box=$('graph-inspector'),left=data.nodes.find(n=>n.id===e.source),right=data.nodes.find(n=>n.id===e.target);box.replaceChildren(el('div','RELATION / SOURCE CHECK','section-kicker'),el('h3',e.label));
  for(const n of [left,right]){const b=el('button',n.title,'graph-related');b.onclick=()=>selectNode(n.id);box.append(b);}
  const notes={shared:'两篇论文的原文中提到了同一概念。',cooccurrence:'两篇论文分别提及语料中经常共同出现的实体。',path:'箭头表示原文关系在候选路径中的接续顺序。',citation:'这条引用方向来自检索服务实际返回的 references / citations 字段。'};box.append(el('p',notes[e.type],'graph-description'));
  if(e.type==='shared')for(const item of e.evidence){box.append(el('h4',item.entity));for(const m of item.mentions)box.append(el('p',`“${m.mention}” · ${m.paper_id===left.id?'第一篇':'第二篇'} · 窗口 ${m.passage_id}`,'graph-quote'));}
  else if(e.type==='cooccurrence')for(const item of e.evidence)box.append(el('p',`${item.source_entity} ↔ ${item.target_entity}：${item.windows} 个共现窗口 / ${item.papers} 篇论文，收缩后分数 ${item.score.toFixed(3)}`,'graph-quote'));
  else if(e.type==='path'){box.append(el('p',e.selected?'已进入生成上下文':'仅候选，未进入生成上下文','graph-status'));for(const c of e.evidence)claimCard(box,c);const pre=el('pre',JSON.stringify(e.checks,null,2),'graph-checks');box.append(el('h4','条件对齐检查'),pre);}
  else box.append(el('p',e.evidence,'fine'));
 }
 function claimCard(box,c){const label=names();const card=el('div',undefined,'graph-claim');card.append(el('strong',`${label[c.source]||c.source} → ${label[c.target]||c.target}`),el('p',c.quote,'graph-quote'),el('p',`条件：${Object.entries(c.conditions||{}).map(([k,v])=>`${k}: ${v}`).join('；')}`,'fine'));const n=data.nodes.find(n=>n.id===c.paper_id);if(n){const b=el('button',n.title,'graph-related');b.onclick=()=>{phase='pool';mode='local';picked=n.id;edgePicked=null;neighborhoodPage=0;render();};card.append(b);}box.append(card);}
 function renderPaths(){const box=$('graph-path-list');box.replaceChildren();const paths=data.paths||[];const cross=paths.filter(p=>new Set(p.paper_ids).size>1);box.append(el('p',`候选 ${paths.length} 条 · 跨论文 ${cross.length} 条 · 最终采用 ${paths.filter(p=>p.selected).length} 条 · 被拒绝的接续 ${(data.rejected_links||[]).length} 条`,'graph-status'));
  if(!cross.length)box.append(el('p','本次暂无跨论文路径，可继续查看共同概念与引用关联。','graph-description'));
  const unselected=el('details');unselected.append(el('summary',`其余候选路径 · ${paths.filter(p=>!p.selected).length} 条（未进入回答）`));
  for(const p of [...paths].sort((a,b)=>Number(b.selected)-Number(a.selected))){const d=el('details'),s=el('summary',`${p.selected?'已采用':'仅候选'} · ${p.paper_ids.length} 篇论文 · ${p.relations.length} 段关系 · ${p.state==='uncertain'?'条件未充分对齐':'原文报告的关系'}`);d.append(s);for(const c of p.relations)claimCard(d,c);(p.selected?box:unselected).append(d);}if(paths.some(p=>!p.selected))box.append(unselected);
  if(data.rejected_links?.length){const d=el('details');d.append(el('summary','查看被拒绝的连接及条件冲突'),el('pre',JSON.stringify(data.rejected_links,null,2),'graph-checks'));box.append(d);}
 }
 function transform(){$('graph-viewport').setAttribute('transform',`translate(${pan.x},${pan.y}) scale(${zoom})`);}
 function resetView(){const ps=[...positions.values()];zoom=Math.min(1,mapWidth/Math.max(mapWidth,...ps.map(p=>p.x+130)),mapHeight/Math.max(mapHeight,...ps.map(p=>p.y+62)));pan={x:0,y:0};transform();}
 $('graph-strength').onchange=draw;$('graph-density').onchange=draw;$('graph-search').oninput=()=>{mode='directory';directoryPage=0;draw();};$('graph-paper-list').onchange=e=>{if(e.target.value)selectNode(e.target.value);};
 $('graph-close-inspector').onclick=()=>{detailOpen=false;edgePicked=null;draw();};
 $('graph-fullscreen').onclick=()=>{const full=document.body.classList.toggle('graph-fullscreen');$('graph-fullscreen').textContent=full?'退出全屏':'放大查看';$('graph-fullscreen').setAttribute('aria-pressed',String(full));};
 document.addEventListener('keydown',e=>{if(e.key==='Escape'&&document.body.classList.contains('graph-fullscreen'))$('graph-fullscreen').click();});
 $('graph-clear').onclick=()=>{picked=null;edgePicked=null;detailOpen=false;neighborhoodPage=0;$('graph-search').value='';draw();};$('graph-reset').onclick=resetView;
 $('graph-plus').onclick=()=>{zoom=Math.min(3,zoom*1.2);transform();};$('graph-minus').onclick=()=>{zoom=Math.max(.4,zoom/1.2);transform();};
 let dragging=null,dragMoved=false;
 const network=$('paper-network');const point=e=>{const p=network.createSVGPoint();p.x=e.clientX;p.y=e.clientY;return p.matrixTransform(network.getScreenCTM().inverse());};
 network.addEventListener('wheel',e=>{if(!e.ctrlKey&&!e.metaKey)return;e.preventDefault();const p=point(e),old=zoom;zoom=Math.max(.4,Math.min(3,zoom*(e.deltaY>0?.9:1.1)));pan={x:p.x-(p.x-pan.x)*zoom/old,y:p.y-(p.y-pan.y)*zoom/old};transform();},{passive:false});
 network.onpointerdown=e=>{if(e.button!==0)return;stopMotion();const p=point(e);dragMoved=false;dragging={id:e.target.closest('[data-paper]')?.getAttribute('data-paper'),edge:e.target.closest('[data-edge]')?.getAttribute('data-edge'),last:p};network.setPointerCapture(e.pointerId);};
 network.onpointermove=e=>{if(!dragging)return;const p=point(e),dx=p.x-dragging.last.x,dy=p.y-dragging.last.y;if(Math.abs(dx)+Math.abs(dy)>1)dragMoved=true;if(dragging.id){const pos=positions.get(dragging.id);pos.x+=dx/zoom;pos.y+=dy/zoom;draw();}else{pan.x+=dx;pan.y+=dy;transform();}dragging.last=p;};
 network.onpointerup=e=>{const id=dragging?.id,edge=dragging?.edge;dragging=null;network.releasePointerCapture(e.pointerId);if(!dragMoved&&id)selectNode(id);else if(!dragMoved&&edge){const record=visibleEdges.find(x=>x.id===edge);if(record)selectEdge(record);}};network.onpointercancel=()=>{dragging=null;};
})();
