/* Data-backed animated research scenes. Nodes always refer to recorded objects. */
window.createResearchScene=function(host){
 const NS='http://www.w3.org/2000/svg',A=v=>Array.isArray(v)?v:[],pid=p=>p?.paperId||p?.paper_id||p?.id||p?.title;
 const titles=['这项研究要查哪些问题','各个方向找到了哪些论文','哪些论文进入了分析','论文原句说了什么','这些发现能否放在一起比较','研究回答用了哪些原文'];
 let data=null,key='',animations=[],paused=false,visible=true,strokes=[],reveals=[],htmlMoves=[],selectedDirection='all',filterDestination='selected',sceneRun='',scenePhase=-1,seenItems=new Set(),settled=Promise.resolve(),retrievalCues=[];
 let relationPaper='all',relationType='all',inspectorTrigger=null;
 const seenVisuals=new Set(),scrollPositions=new Map(),openDetails=new Set();
 let citedBlock=0,citedSource=null;
 const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!=null)n.textContent=text;if(cls)n.className=cls;return n;};
 host.className='research-canvas';
 host.innerHTML='<div class="rc-heading"><div><span class="rc-eyebrow">研究过程</span><h3 class="rc-title"></h3></div><span class="rc-scene-state" role="status"></span></div><div class="rc-scroll"><div class="rc-stage"></div></div><aside class="rc-inspector" hidden aria-label="图中对象详情"><button type="button" class="rc-close" aria-label="关闭图中详情">×</button><div class="rc-inspector-body"></div></aside>';
 const q=s=>host.querySelector(s),stage=q('.rc-stage');
 function S(tag,attrs={},parent=null){const n=document.createElementNS(NS,tag);for(const [k,v]of Object.entries(attrs))n.setAttribute(k,String(v));parent?.append(n);return n;}
 function inspect(title,lines,tag='已记录的内容'){
  inspectorTrigger=document.activeElement;data?.onInspect?.();const box=q('.rc-inspector-body');box.replaceChildren(el('span',tag,'rc-eyebrow'),el('h4',title));for(const line of lines.filter(Boolean))box.append(el('p',String(line)));q('.rc-inspector').hidden=false;q('.rc-close').focus({preventScroll:true});
 }
 function once(list,item,identity){const token=`${data.phase}:${identity}`;if(seenVisuals.has(token))return;seenVisuals.add(token);list.push(item);}
 function appear(node,identity,delay=0){once(htmlMoves,{node,delay},identity);}
 function boardEmpty(parent,title,description){const box=el('div',null,'rc-state-card');box.dataset.state=data.info.status;box.append(el('span',data.info.status==='error'?'!':'◇','rc-state-symbol'),el('h4',title),el('p',description));parent.append(box);}
 function unique(items){return [...new Map(items.filter(Boolean).map(p=>[pid(p),p])).values()];}
 function latest(test){return [...data.records].reverse().find(test)?.output||{};}
 function plan(){return data.result?.research_plan||latest(s=>s.output?.plan).plan||{};}
 function dimensions(){return A(plan().dimensions);}
 function searches(){return data.records.filter(s=>s.kind==='http'&&s.input?.query);}
 function selection(){return latest(s=>s.output?.selected_papers);}
 function scope(){return data.result?.evidence_scope||latest(s=>s.output?.unique_papers!==undefined&&s.output?.dimensions);}
 function summary(textValue){stage.setAttribute('aria-description',textValue);}
 function planning(){
  const ds=dimensions(),root=board();root.classList.add('rc-plan-board');summary(`${ds.length} 个研究方向`);
  const question=el('article',null,'rc-plan-question');question.append(el('span','研究问题','rc-column-label'),el('h4',data.run.question),el('p',ds.length?`沿 ${ds.length} 个方向查找论文`:'等待研究方向'));root.append(question);appear(question,'question:'+data.run.question);
  const topicQueries=A(plan().topic_queries);
  if(topicQueries.length){
   const detail=el('details',null,'rc-query-detail rc-topic-queries');detail.dataset.detailKey='topic-queries';detail.append(el('summary','围绕原问题的检索词'));
   for(const query of topicQueries)detail.append(el('p',query));question.append(detail);
  }
  const branches=el('div',null,'rc-plan-branches');root.append(branches);
  const links=S('svg',{'aria-hidden':'true',class:'rc-plan-lines rc-branch-link'},root);
  for(const [i,d]of ds.entries()){
   const branch=el('article',null,'rc-plan-branch'),number=el('span',String(i+1).padStart(2,'0'),'rc-branch-number'),content=el('div',null,'rc-branch-content');
   const line=S('path',{d:'M0 0h1'},links);once(strokes,{node:line,delay:60+i*70},'plan-link:'+d.id);
   content.append(el('h4',d.label));const detail=el('details',null,'rc-query-detail');detail.dataset.detailKey='direction:'+d.id;detail.append(el('summary','查看检索词'));
   if(d.query)detail.append(el('p',d.query));if(d.followup_query&&d.followup_query!==d.query)detail.append(el('p','备选检索词 · '+d.followup_query));if(!d.query&&!d.followup_query)detail.append(el('p','检索词尚未记录。'));content.append(detail);branch.append(number,content);branches.append(branch);appear(content,'direction:'+JSON.stringify(d),160+i*70);
  }
  if(!ds.length){
   const pending=data.info.status==='running'||data.info.status==='waiting';
   boardEmpty(branches,pending?'等待研究方向':data.info.status==='error'?'问题规划暂时中断':'未记录研究方向',pending?'方向确定后，可以查看每个方向的检索词。':'这份记录中仅保存了研究问题。');
  }
 }
 function alignPlanLinks(){
  const svg=stage.querySelector('.rc-plan-lines');if(!svg||!svg.childElementCount)return;
  const root=svg.parentElement,rect=root.getBoundingClientRect(),question=root.querySelector('.rc-plan-question').getBoundingClientRect();
  if(!rect.width||!rect.height)return;
  svg.setAttribute('viewBox',`0 0 ${rect.width} ${rect.height}`);
  const branches=root.querySelectorAll('.rc-plan-branch');
  const stacked=branches[0].getBoundingClientRect().top>=question.bottom-1;
  const originX=stacked?branches[0].getBoundingClientRect().left-rect.left-14:question.right-rect.left;
  const originY=stacked?question.bottom-rect.top:question.top-rect.top+question.height/2;
  branches.forEach((branch,i)=>{
   const edge=branch.getBoundingClientRect().left-rect.left,number=branch.querySelector('.rc-branch-number').getBoundingClientRect(),y=number.top-rect.top+number.height/2;
   const mid=(originX+edge)/2;
   svg.children[i].setAttribute('d',stacked?`M${originX} ${originY}V${y-7}Q${originX} ${y} ${originX+7} ${y}H${edge}`:`M${originX} ${originY}C${mid} ${originY} ${mid} ${y} ${edge} ${y}`);
  });
 }
 function belongsToDirection(search,d){
  if(search.input?.dimension)return search.input.dimension===d.id;
  return [d.query,d.followup_query,...A(d.queries)].includes(search.input?.query);
 }
 function searchDirections(records){
  const directions=dimensions(),queries=A(plan().topic_queries);
  return records.some(s=>s.input.dimension==='topic'||(!s.input.dimension&&queries.includes(s.input.query)))
   ?[{id:'topic',label:'围绕原问题',queries},...directions]:directions;
 }
 function action(label,fn,cls=''){const b=el('button',label,cls);b.type='button';b.onclick=fn;return b;}
 function browse(fn){data.onBrowse?.();data.following=false;fn();key='';update(data);const target=data.phase===1?[...stage.querySelectorAll('[data-direction]')].find(b=>b.dataset.direction===selectedDirection):stage.querySelector('.rc-outcome-tabs [aria-pressed=true]');target?.focus({preventScroll:true});}
 function board(){stage.classList.add('rc-stage-board');const box=el('div',null,'rc-paper-board');stage.append(box);return box;}
 function countHeading(label,count){const h=el('div',null,'rc-column-heading');h.append(el('span',label),el('strong',`${count} 篇`));return h;}
 function card(p,i,status,identity){
  const b=action('',()=>inspect(p.title||'论文',[status,p.exclusion_reason,p.abstract||p.text||'此条记录没有摘要。'],'论文来源'),'rc-full-paper');
  b.dataset.paperId=pid(p);b.setAttribute('aria-label',p.title||'论文');
  const icon=el('span',String(i+1).padStart(2,'0'),'rc-document-number');icon.setAttribute('aria-hidden','true');
  const words=el('span',null,'rc-paper-words');words.append(el('strong',p.title||'未命名论文'));
  const meta=[p.year,status].filter(Boolean).join(' · ');if(meta)words.append(el('small',meta));
  b.append(icon,words);if(!seenItems.has(identity)){seenItems.add(identity);htmlMoves.push({node:b,delay:Math.min(htmlMoves.length,8)*35+(data.phase===1?180:0)});}return b;
 }
 function paperColumn(parent,ps,label,scrollKey,status){
  const col=el('section',null,'rc-paper-column');col.append(countHeading(label,ps.length));
  const list=el('div',null,'rc-complete-papers');list.dataset.scrollKey=scrollKey;list.setAttribute('role','region');list.setAttribute('aria-label',label+'完整列表');list.tabIndex=0;
  ps.forEach((p,i)=>list.append(card(p,i,typeof status==='function'?status(p):status,`${data.phase}:${scrollKey}:${pid(p)}`)));
  if(!ps.length)list.append(el('p',data.info.status==='error'?'本次检索未完成':data.info.status==='running'?'等待新论文返回…':'暂无论文记录','rc-board-empty'));
  col.append(list);parent.append(col);return col;
 }
 function channel(parent){
  const connector=el('div',null,'rc-results-connector');connector.setAttribute('aria-hidden','true');
  const arrow=S('svg',{viewBox:'0 0 88 26','aria-hidden':'true'},connector);
  const line=S('path',{d:'M3 13H79M70 5L79 13L70 21',class:'rc-result-arrow'},arrow);
  once(strokes,{node:line,delay:80},'retrieval-link:'+selectedDirection);parent.append(connector);
 }
 function alignRetrievalLink(){
  alignPlanLinks();
  const connector=stage.querySelector('.rc-results-connector'),active=stage.querySelector('.rc-direction-button[aria-pressed=true]'),heading=stage.querySelector('.rc-found-heading');
  if(!connector||!active||!heading)return;
  const r=connector.getBoundingClientRect(),a=active.getBoundingClientRect(),h=heading.getBoundingClientRect();if(!r.width||!r.height)return;
  const x1=a.right-r.left+1,x2=h.left-r.left-2,mid=(x1+x2)/2;
  const y1=a.top+a.height/2-r.top,y2=h.top+h.height/2-r.top;
  connector.querySelector('svg').setAttribute('viewBox',`0 0 ${r.width} ${r.height}`);
  connector.querySelector('path').setAttribute('d',`M${x1} ${y1} C${mid} ${y1} ${mid} ${y2} ${x2} ${y2} M${x2-7} ${y2-6} L${x2} ${y2} L${x2-7} ${y2+6}`);
 }
 let inspectedBatch=null;
 function retrievalGroups(records,directions){
  const groups=new Map(['all',...directions.map(d=>d.id)].map(id=>[id,{queries:[],byPaper:new Map(),batches:[]}]));
  for(const search of records){
   const explicit=search.input.dimension;
   const ids=explicit?(explicit!=='all'&&groups.has(explicit)?[explicit]:[]):directions.filter(d=>belongsToDirection(search,d)).map(d=>d.id);
   const returned=Array.isArray(search.output?.papers)?unique(search.output.papers):null;
   for(const id of ['all',...ids]){
    const {queries,byPaper,batches}=groups.get(id);
    queries.push(search);
    if(!returned)continue;
    const addedIds=[];
    for(const paper of returned){
     const paperId=pid(paper);if(!byPaper.has(paperId))addedIds.push(String(paperId));
     byPaper.set(paperId,paper);
    }
    batches.push({id:String(search.id??search.seq??batches.length),query:search.input.query,supplemental:search.input.supplemental,
     addedIds,returned:returned.length,total:byPaper.size});
   }
  }
  return groups;
 }
 function batchHistory(batches,direction,list){
  if(!batches.length)return null;
  const root=el('section',null,'rc-batch-history'),label=el('label',null,'rc-batch-label');
  const picker=el('select',null,'rc-batch-picker');picker.dataset.batchId=direction;picker.setAttribute('aria-label','查看检索批次');
  for(const [i,batch] of batches.entries())picker.append(new Option(`第 ${i+1} 批${batch.supplemental?' · 补充搜索':''}`,batch.id));
  label.append(el('span','检索批次'),picker);root.append(label);
  const plot=el('div',null,'rc-batch-plot'),chart=S('svg',{viewBox:'0 0 180 46',role:'img','aria-label':'各批次合并去重后的累计论文数'},plot);
  const end=batches.at(-1).total,points=batches.map((b,i)=>[5+169*(i+1)/batches.length,38-30*b.total/Math.max(1,end)]);
  const segments=points.map(([x,y])=>`H${x}V${y}`),shape='M5 38'+segments.join('');
  S('path',{d:'M5 38H174',class:'rc-batch-base'},chart);
  S('path',{d:shape+'V38Z',class:'rc-batch-area'},chart);
  if(points.length>1)S('path',{d:'M5 38'+segments.slice(0,-1).join(''),class:'rc-batch-past'},chart);
  const [fromX,fromY]=points.at(-2)||[5,38],last=batches.at(-1);
  const path=S('path',{d:`M${fromX} ${fromY}`+segments.at(-1),class:'rc-batch-trend'},chart),marker=S('circle',{r:3.4,class:'rc-batch-marker'},chart);
  once(strokes,{node:path,delay:60},'batch-plot:'+JSON.stringify([direction,last.id,last.total]));
  const tally=el('strong');plot.append(tally);root.append(plot);
  const note=el('div',null,'rc-batch-note'),counts=el('span'),change=el('strong',null,'rc-batch-change'),repeated=el('span'),query=el('span',null,'rc-batch-query');note.setAttribute('aria-live','polite');
  counts.append(change,repeated);note.append(counts,query);root.append(note);
  function show(index){
   const batch=batches[index],[x,y]=points[index];picker.selectedIndex=index;
   tally.textContent=`累计 ${batch.total} 篇`;
   marker.setAttribute('cx',x);marker.setAttribute('cy',y);
   change.textContent=`本批新增 ${batch.addedIds.length} 篇`;repeated.textContent=` · 与此前重复 ${batch.returned-batch.addedIds.length} 篇`;
   query.textContent=batch.query||'检索词未记录';
  }
  let cardsById,marked=[];
  function markAdditions(batch,scroll){
   for(const card of marked){delete card.dataset.batchNew;card.removeAttribute('aria-description');}
   if(!cardsById)cardsById=new Map([...list.querySelectorAll('.rc-full-paper')].map(card=>[card.dataset.paperId,card]));
   marked=batch.addedIds.map(id=>cardsById.get(id)).filter(Boolean);
   for(const card of marked){card.dataset.batchNew='true';card.setAttribute('aria-description','在选中的批次中首次找到');}
   if(scroll&&marked.length){
    const target=marked[0].getBoundingClientRect(),frame=list.getBoundingClientRect();
    if(target.top<frame.top||target.bottom>frame.bottom)list.scrollTop+=target.top-frame.top-4;
   }
  }
  const historyKey=JSON.stringify([data.run.id,direction]);
  const index=inspectedBatch?.key===historyKey&&!data.following?batches.findIndex(b=>b.id===inspectedBatch.id):-1;
  show(index>=0?index:batches.length-1);
  if(index>=0)markAdditions(batches[index],false);
  picker.onchange=()=>{
   data.onBrowse?.();data.following=false;inspectedBatch={key:historyKey,id:picker.value};
   show(picker.selectedIndex);markAdditions(batches[picker.selectedIndex],true);
  };
  return root;
 }
 function retrieval(){
  const root=board(),ss=searches().filter(s=>!s.output?.retry_scheduled&&!/连接重试/.test(s.name||'')),ds=searchDirections(ss);
  const pending=data.info.status==='running'||data.info.status==='waiting';
  const noSearch=pending?'等待检索结果':'未记录检索';
  root.classList.add('rc-retrieval-board');
  if(selectedDirection!=='all'&&!ds.some(d=>d.id===selectedDirection))selectedDirection='all';
  const nav=el('nav',null,'rc-direction-list');nav.setAttribute('aria-label','选择检索方向');
  nav.append(el('div','检索方向','rc-column-label'));
  const options=[{id:'all',label:'全部方向'},...ds];
  const byDirection=retrievalGroups(ss,ds);
  options.forEach(d=>{const {queries,byPaper}=byDirection.get(d.id),count=byPaper.size;
   const searching=data.run.status==='running'&&queries.some(s=>!s.status||s.status==='running');
   const label=searching?(count?`正在补充搜索 · 已找到 ${count} 篇`:'正在搜索…'):count?`${count} 篇论文`:queries.some(s=>s.status==='error')?'检索未完成':queries.some(s=>s.status==='success')?'未找到论文':noSearch;
   const b=action('',()=>browse(()=>{selectedDirection=d.id;}),'rc-direction-button');b.dataset.direction=d.id;b.setAttribute('aria-pressed',String(selectedDirection===d.id));b.append(el('strong',d.label),el('span',label));nav.append(b);
  });root.append(nav);channel(root);
  const direction=ds.find(d=>d.id===selectedDirection),{byPaper,queries:currentQueries,batches}=byDirection.get(selectedDirection);
  const papers=[...byPaper.values()],origins=new Map();
  for(const d of ds)for(const id of byDirection.get(d.id).byPaper.keys()){
   if(!origins.has(id))origins.set(id,[]);
   origins.get(id).push(d.label);
  }
  const col=paperColumn(root,papers,direction?direction.label:'全部候选论文','retrieval:'+selectedDirection,p=>{const names=origins.get(pid(p));return names?.length?'来自：'+names.join('、'):'';});
  const heading=col.querySelector('.rc-column-heading');heading.classList.add('rc-found-heading');
  const searching=data.run.status==='running'&&currentQueries.some(s=>!s.status||s.status==='running');
  heading.setAttribute('aria-live','polite');
  heading.replaceChildren(el('span',direction?direction.label:'全部方向 · 合并重复论文'),el('strong',searching?(papers.length?`正在补充搜索 · 已找到 ${papers.length} 篇论文`:'正在搜索相关论文…'):papers.length?`找到 ${papers.length} 篇论文`:data.info.status==='error'?'检索未完成':currentQueries.some(s=>s.status==='success')?'未找到论文':noSearch));
  const history=batchHistory(batches,selectedDirection,col.querySelector('.rc-complete-papers'));
  if(history)heading.after(history);
  const active=nav.querySelector('[aria-pressed=true]');if(active)once(retrievalCues,{node:active,delay:0},'direction-cue:'+selectedDirection);
  col.classList.add('rc-retrieved-column');
  if(direction&&!history){const queries=el('details',null,'rc-query-detail');queries.dataset.detailKey='search:'+direction.id;queries.append(el('summary','检索词'));for(const query of new Set(currentQueries.map(s=>s.input.query)))queries.append(el('p',query));col.append(queries);}
 }
 let locatedCandidate=null;
 function selectionIndex(root,all,selectedIds,excludedIds,papers,indexById,pending){
  const box=el('section',null,'rc-selection-index');
  const caption=el('div',null,'rc-index-caption');
  caption.append(el('strong','候选论文去向 · 按编号排列'));
  const unrecorded=all.length-selectedIds.size-excludedIds.size;
  const legend=el('div',null,'rc-index-legend');
  for(const [name,label,count] of [['selected','进入分析',selectedIds.size],['excluded','未选入',excludedIds.size],['unknown',pending?'待筛选':'未记录',unrecorded]]){
   if(!count)continue;
   const item=el('span',label+' '+count);item.dataset.outcome=name;legend.append(item);
  }
  caption.append(legend);box.append(caption);
  const band=el('div',null,'rc-index-band');box.append(band);
  const chart=S('svg',{viewBox:'0 0 1000 19',preserveAspectRatio:'none',class:'rc-index-plot',role:'img','aria-label':'按候选编号顺序表示每篇论文的去向'},band);
  const pointer=el('span',null,'rc-index-pointer');pointer.hidden=true;pointer.setAttribute('aria-hidden','true');band.append(pointer);
  const marks={selected:[],excluded:[],unknown:[]},unit=1000/all.length;
  all.forEach((paper,i)=>{
   const id=String(pid(paper)),state=selectedIds.has(id)?'selected':excludedIds.has(id)?'excluded':'unknown';
   const height=state==='selected'?17:state==='excluded'?9:4;
   const start=i*unit,end=(i+1)*unit-Math.min(1.8,unit*.17);
   marks[state].push(`M${start} 18V${18-height}H${end}V18Z`);
  });
  for(const [state,segments] of Object.entries(marks)){
   if(!segments.length)continue;
   const path=S('path',{d:segments.join(''),'data-outcome':state},chart);
   if(state==='selected')once(reveals,{node:path,delay:80},'indexed-selection:'+JSON.stringify([...selectedIds].map(id=>indexById.get(id))));
  }
  if(!papers.length)return box;
  const locator=el('div',null,'rc-index-locator'),result=el('p',null,'rc-located-title');
  result.setAttribute('role','status');result.hidden=true;
  const rows=new Map();
  for(const card of root.querySelectorAll('.rc-full-paper')){
   const id=card.dataset.paperId;
   if(!rows.has(id))rows.set(id,[]);
   rows.get(id).push(card);
  }
  let previous=[];
  function locate(paper,interactive=true){
   const id=String(pid(paper)),number=indexById.get(id);
   if(interactive){
    data.onBrowse?.();data.following=false;
    locatedCandidate={run:data.run.id,destination:filterDestination,id};
   }
   for(const row of previous)delete row.dataset.located;
   previous=rows.get(id)||[];
   for(const row of previous){
    row.dataset.located='true';
    if(!interactive)continue;
    const list=row.closest('.rc-complete-papers'),target=row.getBoundingClientRect(),frame=list.getBoundingClientRect();
    if(target.top<frame.top||target.bottom>frame.bottom)list.scrollTop+=target.top-frame.top-4;
   }
   pointer.style.left=((number-.5)/all.length*100)+'%';pointer.hidden=false;
   for(const chip of locator.querySelectorAll('button'))chip.setAttribute('aria-pressed',String(chip.dataset.paperId===id));
   const select=locator.querySelector('select');if(select)select.value=id;
   result.textContent=`候选 ${number} · ${paper.title||'未命名论文'}`;result.hidden=false;
  }
  const label=filterDestination==='selected'?'定位入选编号':'定位未选入编号';
  if(papers.length<=12){
   locator.append(el('span',label));
   for(const paper of papers){
    const id=String(pid(paper)),number=indexById.get(id),b=action(String(number).padStart(2,'0'),()=>locate(paper),'rc-locate-paper');
    b.dataset.paperId=id;b.dataset.paperLocator=id;b.title=paper.title;b.setAttribute('aria-label',`定位候选第 ${number} 篇：${paper.title}`);b.setAttribute('aria-pressed','false');locator.append(b);
   }
  }else{
   const select=el('select',null,'rc-locate-select'),wrapper=el('label',label),placeholder=new Option('选择论文编号','');placeholder.disabled=true;select.dataset.paperLocator=filterDestination;select.append(placeholder);
   for(const paper of papers)select.append(new Option(indexById.get(String(pid(paper)))+' · '+paper.title,pid(paper)));
   select.onchange=()=>{if(select.selectedIndex)locate(papers[select.selectedIndex-1]);};wrapper.append(select);locator.append(wrapper);
  }
  if(locatedCandidate?.run===data.run.id&&locatedCandidate.destination===filterDestination){
   const paper=papers.find(p=>String(pid(p))===locatedCandidate.id);if(paper)locate(paper,false);
  }
  box.append(locator,result);return box;
 }
 function filtering(){
  const se=selection(),ready=Array.isArray(se.selected_papers),selected=unique(A(se.selected_papers));
  const selectedIds=new Set(selected.map(p=>String(pid(p))));
  const excluded=unique(A(se.excluded_papers)).filter(p=>!selectedIds.has(String(pid(p))));
  const excludedIds=new Set(excluded.map(p=>String(pid(p))));
  const found=unique(searches().flatMap(s=>A(s.output?.papers)));
  const all=ready?unique([...found,...selected,...excluded]):found;
  const pending=!ready&&['waiting','running'].includes(data.info.status);
  const root=board();root.classList.add('rc-filter-board');root.dataset.destination=filterDestination;
  const summary=el('div',null,'rc-selection-summary');
  summary.append(el('strong',ready?`记录到 ${all.length} 篇候选，${selected.length} 篇进入分析`:data.info.status==='running'?'正在挑选要阅读的论文':pending?'等待筛选':'未记录筛选结果'));root.append(summary);
  const tabs=el('div',null,'rc-outcome-tabs');tabs.setAttribute('role','group');tabs.setAttribute('aria-label','筛选去向');
  for(const [id,label,ps] of [['selected','进入分析',selected],['excluded','未选入',excluded]]){
   const count=Array.isArray(se[id+'_papers'])?`${ps.length} 篇`:pending?'待筛选':'未记录';
   const b=action(`${label} · ${count}`,()=>browse(()=>{filterDestination=id;}));b.setAttribute('aria-pressed',String(filterDestination===id));tabs.append(b);
  }
  summary.append(tabs);
  const candidates=paperColumn(root,all,'全部候选论文','candidates',p=>pending?'等待筛选':selectedIds.has(String(pid(p)))?'✓ 进入分析':p.exclusion_reason||(excludedIds.has(String(pid(p)))?'未选入':'未记录筛选结果'));candidates.classList.add('rc-candidate-column');
  const output=el('section',null,'rc-paper-column rc-outcome-column');root.append(output);
  const papers=filterDestination==='selected'?selected:excluded;
  const col=paperColumn(output,papers,filterDestination==='selected'?'已选中的论文':'未选入的论文','outcome:'+filterDestination,filterDestination==='selected'?'✓ 进入后续证据分析':p=>p.exclusion_reason||'未选入本次分析');col.classList.add('rc-outcome-papers');
  const indexById=new Map(all.map((p,i)=>[String(pid(p)),i+1]));
  for(const c of root.querySelectorAll('.rc-full-paper')){
   const number=indexById.get(c.dataset.paperId),badge=c.querySelector('.rc-document-number');
   badge.textContent=String(number).padStart(2,'0');badge.title=`候选论文第 ${number} 篇`;
   c.setAttribute('aria-label',`候选论文第 ${number} 篇：${c.querySelector('strong').textContent}`);
   c.classList.toggle('rc-paper-picked',selectedIds.has(c.dataset.paperId));
  }
  if(all.length)summary.append(selectionIndex(root,all,selectedIds,excludedIds,papers,indexById,pending));
 }
 const relationNames={reported_causal:'论文报告的影响',associated_with:'相关性观察',hypothesis:'待验证假设'};
 const conditionNames={task:'研究任务',model:'模型',dataset:'数据集',metric:'衡量指标',setting:'研究情境',population:'研究人群',period:'研究时段',method:'研究方法',assumptions:'前提假设',bridge_state:'中间因素变化'};
 const checkNames={compatible:'条件相符',conflict:'存在差异',unknown:'条件待补充'};
 const stateNames={increases:'增加',decreases:'减少',present:'出现'};
 const evidenceChoice={run:null,claim:null,check:null};
 function evidencePapers(){
  const papers=new Map(data.papers.map(p=>[pid(p),p.title]));
  for(const p of A(data.result?.sources)){
   if(p.title&&pid(p))papers.set(pid(p),p.title);
   if(p.title&&p.passage_id)papers.set(p.passage_id,p.title);
  }
  for(const r of data.records){
   for(const [id,title] of Object.entries(r.input?.paper_titles||{}))if(title)papers.set(id,title);
   for(const p of A(r.input?.passages))if(p.paper_id&&(p.title||r.input?.paper))papers.set(p.paper_id,p.title||r.input.paper);
   for(const c of A(r.output?.claims))if(r.input?.paper)papers.set(c.paper_id,r.input.paper);
  }
  return papers;
 }
 function concept(id){return data.labels?.[id]||(!id||/^[a-f0-9]{20}$/i.test(id)?'':id);}
 function original(claim){return claim?.evidence?.quote||claim?.quote||'';}
 function evidenceDrawing(parent,cls,height){
  const svg=S('svg',{preserveAspectRatio:'none','aria-hidden':'true',class:cls},parent);
  // Keep drawing lengths in rendered pixels, including when the panel is narrow.
  const width=svg.getBoundingClientRect().width||100;
  svg.setAttribute('viewBox','0 0 '+width+' '+height);
  return {svg,width};
 }
 function valueText(value){
  if(value==null||/^(?:unknown|unspecified|not stated|none|null|general)?$/i.test(String(value).trim()))return '未说明';
  return stateNames[value]||String(value);
 }
 function quoteWithTerms(claim){
  const quote=original(claim),block=el('blockquote',null,'em-quote');
  if(!quote){block.textContent='这条记录未保存原句。';return block;}
  // Highlight only a literal occurrence. Canonical labels can differ from the author's wording.
  const hits=[];
  for(const side of ['source','target']){
   const term=data.labels?.[claim[side]]||claim[side];
   if(typeof term!=='string'||!term.length)continue;
   const escaped=term.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
   const hit=new RegExp(escaped,'iu').exec(quote);
   if(hit)hits.push({at:hit.index,end:hit.index+hit[0].length,side});
  }
  let offset=0;
  for(const hit of hits.sort((a,b)=>a.at-b.at||b.end-a.end)){
   if(hit.at<offset)continue;
   block.append(document.createTextNode(quote.slice(offset,hit.at)),el('mark',quote.slice(hit.at,hit.end),'em-term-'+hit.side));
   offset=hit.end;
  }
  block.append(document.createTextNode(quote.slice(offset)));
  return block;
 }
 function evidenceBrowser(root,{kind,entries,focusPanel,renderFocus}){
  if(evidenceChoice.run!==data.run.id){evidenceChoice.run=data.run.id;evidenceChoice.claim=null;evidenceChoice.check=null;}
  const layout=el('div',null,'em-browser'),list=el('div',null,kind==='claim'?'em-index rc-relations-list':'em-index rc-check-list');
  list.dataset.scrollKey=kind==='claim'?'relations:'+relationPaper+':'+relationType:'checks';
  list.setAttribute('role','group');list.setAttribute('aria-label',kind==='claim'?'选择原文关系':'选择条件核对记录');
  const activeId=evidenceChoice[kind],follow=data.run.status==='running'&&data.following;
  let selected=(!follow&&entries.find(entry=>entry.id===activeId))||(follow?entries.at(-1):entries[0]);
  function showChoice(button){
   const item=button.getBoundingClientRect(),area=list.getBoundingClientRect();
   if(item.bottom>area.bottom)list.scrollTop+=item.bottom-area.bottom;
   else if(item.top<area.top)list.scrollTop-=area.top-item.top;
  }
  list.setAttribute('aria-description','用上下方向键切换，Home 和 End 跳至首尾。');
  function select(entry,manual){
   if(manual){data.onBrowse?.();data.following=false;}
   if(manual&&selected===entry)return;
   if(manual)for(const detail of focusPanel.querySelectorAll('[data-detail-key]')){
    if(detail.open)openDetails.add(detail.dataset.detailKey);else openDetails.delete(detail.dataset.detailKey);
   }
   if(selected){selected.button.setAttribute('aria-pressed','false');selected.button.tabIndex=-1;}
   entry.button.setAttribute('aria-pressed','true');entry.button.tabIndex=0;
   selected=entry;evidenceChoice[kind]=entry.id;
   if(manual){strokes.length=0;reveals.length=0;htmlMoves.length=0;retrievalCues.length=0;}
   renderFocus(entry);
   if(manual){
    for(const detail of focusPanel.querySelectorAll('[data-detail-key]'))detail.open=openDetails.has(detail.dataset.detailKey);
    animate();
   }
  }
  for(const entry of entries){
   const button=action('',()=>select(entry,true),kind==='claim'?'rc-relation-card em-choice':'rc-check-item em-choice');
   button.dataset[kind==='claim'?'claimId':'checkId']=entry.id;
   button.setAttribute('aria-pressed','false');button.tabIndex=-1;
   button.append(el('span',String(entry.number).padStart(2,'0'),'em-index-number'),el('span',entry.title,'em-index-label'));
   entry.button=button;list.append(button);
  }
  list.addEventListener('keydown',event=>{
   const i=entries.indexOf(selected),target={ArrowUp:i-1,ArrowDown:i+1,Home:0,End:entries.length-1}[event.key];
   if(target===undefined||event.altKey||event.ctrlKey||event.metaKey)return;
   event.preventDefault();const next=entries[Math.max(0,Math.min(entries.length-1,target))];
   select(next,true);next.button.focus({preventScroll:true});showChoice(next.button);
  });
  layout.append(list,focusPanel);root.append(layout);select(selected,false);
  if(follow)requestAnimationFrame(()=>{
   if(!list.isConnected||!data.following)return;
   showChoice(selected.button);
  });
 }
 function relationships(){
  const all=[...data.claims.values()],papers=evidencePapers(),root=board();root.classList.add('rc-relations-board','em-board');
  if(!all.length){boardEmpty(root,'还没有原文关系',data.info.status==='running'?'读到有依据的关系后，会在这里显示对应的论文原句。':'本次记录未保存可展示的关系。');return;}
  const paperIds=[...new Set(all.map(c=>c.paper_id).filter(Boolean))];
  const toolbar=el('div',null,'em-toolbar'),total=el('span',all.length+' 条原文关系','em-total');
  function filter(label,options,value,kind,onChange){
   const field=el('select');field.setAttribute('aria-label',label);field.dataset.evidenceFilter=kind;
   for(const [id,text] of options)field.append(new Option(text,id));
   field.value=value;field.onchange=()=>{data.onBrowse?.();data.following=false;onChange(field.value);key='';update(data);stage.querySelector('[data-evidence-filter='+kind+']')?.focus({preventScroll:true});};
   return field;
  }
  const paperOptions=[['all','全部来源论文'],...paperIds.map((id,i)=>[id,papers.get(id)||'来源论文 '+(i+1)])];
  const types=[...new Set(all.map(c=>c.type).filter(Boolean))];
  const typeOptions=[['all','全部关系类型'],...types.map(type=>[type,relationNames[type]||type])];
  toolbar.append(total,filter('按来源论文查看关系',paperOptions,relationPaper,'paper',v=>relationPaper=v),filter('按关系类型查看',typeOptions,relationType,'type',v=>relationType=v));root.append(toolbar);
  const entries=all.map((c,i)=>({id:c.id,number:i+1,c,title:[concept(c.source),concept(c.target)].filter(Boolean).join(' 与 ')||original(c)||'原文关系 '+(i+1)}))
   .filter(({c})=>(relationPaper==='all'||c.paper_id===relationPaper)&&(relationType==='all'||c.type===relationType));
  summary('显示 '+entries.length+' 条原文关系，共 '+paperIds.length+' 篇有记录的来源论文');
  if(!entries.length){root.append(el('p','没有符合筛选条件的关系。','rc-board-empty'));return;}
  const panel=el('section',null,'em-focus em-relation-focus');panel.setAttribute('aria-label','所选关系的原句与因素');
  evidenceBrowser(root,{kind:'claim',entries,focusPanel:panel,renderFocus({c,id,number}){
   panel.replaceChildren();panel.dataset.claimId=id;panel.dataset.type=c.type||'unknown';
   const head=el('div',null,'em-head'),origin=el('p',papers.get(c.paper_id)||papers.get(c.passage_id)||'论文标题未记录','em-source');
   head.append(el('span','原文关系 '+String(number).padStart(2,'0'),'em-kicker'),el('span',relationNames[c.type]||'原文关系','em-status'));
   const sentence=quoteWithTerms(c);
   panel.append(head,origin,sentence);
   // Some archived passages preserve the quote but only store opaque concept identifiers.
   if(concept(c.source)||concept(c.target)){
   const identity='factor:'+JSON.stringify([id,c.source,c.target,c.type,original(c)]);
   if(original(c)){
    const fork=el('div',null,'em-fork-wrap');panel.append(fork);
    const {svg,width}=evidenceDrawing(fork,'em-fork',30),mid=width/2;
    for(const [side,end] of [['left',.16],['right',.84]]){
     const d='M'+mid+' 0 V6 Q'+mid+' 12 '+(mid+(end<.5?-6:6))+' 12 H'+(end*width)+' V29';
     once(strokes,{node:S('path',{d},svg),delay:0},identity+':extract-'+side);
    }
   }
   const track=el('div',null,'em-factor-track');
   for(const side of ['source','target']){
    const factor=el('div',null,'em-factor em-factor-'+side);factor.append(el('strong',concept(c[side])||'名称未记录'));
    const state=stateNames[c[side+'_state']];if(state)factor.append(el('small',state));track.append(factor);
    if(side==='source'){
     const connector=el('div',null,'em-relation-link');
     const directed=c.type==='reported_causal'||c.type==='hypothesis';
     const verb=c.type==='hypothesis'?'假设影响':c.type==='reported_causal'?'影响':c.type==='associated_with'?'相关':'关系';
     connector.append(el('span',verb));
     const svg=S('svg',{viewBox:'0 0 82 18','aria-hidden':'true',class:'em-ink'},connector);
     const wire=S('path',{d:'M4 9H77',class:'em-wire'},svg);
     if(directed)S('path',{d:'m69 3 8 6-8 6',class:'em-arrow-tip'},svg);
     once(strokes,{node:wire,delay:190},identity);
     once(reveals,{node:factor,delay:140},identity+':left');
     track.append(connector);
    }
   }
   once(reveals,{node:track.lastElementChild,delay:340},'factor-target:'+JSON.stringify([id,c.target]));
   panel.append(track);
   }
   const conditions=Object.entries(c.conditions||{});
   if(conditions.length){
    const detail=el('details',null,'em-detail');detail.dataset.detailKey='relation:'+id;detail.append(el('summary','查看适用条件'));
    const terms=el('dl',null,'em-terms');for(const [k,v]of conditions)terms.append(el('dt',conditionNames[k]||k),el('dd',valueText(v)));
    detail.append(terms);panel.append(detail);
   }
  }});
 }
 function checking(){
  const analysis=latest(s=>/路径、条件/.test(s.name||''));
  const paths=A(data.result?.candidate_paths||analysis.paths||data.result?.paths);
  const checks=[...A(data.result?.rejected_links||analysis.rejected_links),...paths.flatMap(p=>A(p.checks))],root=board();root.classList.add('rc-check-board','em-board');
  if(checks.length){
   const overview=el('div',null,'em-toolbar'),bar=el('div',null,'em-check-tally'),papers=evidencePapers();
   overview.append(el('span',checks.length+' 项条件核对','em-total'));bar.setAttribute('aria-hidden','true');
   for(const [state,label] of Object.entries(checkNames)){
    const count=checks.filter(c=>(checkNames[c.state]?c.state:'unknown')===state).length;
    if(!count)continue;
    const segment=el('i');segment.dataset.state=state;segment.style.flexGrow=count;bar.append(segment);
    const legend=el('span',label+' '+count,'em-legend');legend.dataset.state=state;overview.append(legend);
   }
   root.append(overview,bar);
   const occurrences=new Map(),entries=checks.map((c,i)=>{
    const pair=JSON.stringify([c.left,c.right]),n=occurrences.get(pair)||0;occurrences.set(pair,n+1);
    const left=data.claims.get(c.left),right=data.claims.get(c.right);
    const shared=left?.target&&left.target===right?.source?concept(left.target):'';
    const bridge=shared||('核对 '+String(i+1).padStart(2,'0'));
    return {id:pair+':'+n,number:i+1,c,left,right,title:bridge+' · '+(checkNames[c.state]||checkNames.unknown)};
   });
   const panel=el('section',null,'em-focus em-check-focus');panel.setAttribute('aria-label','所选核对记录');
   evidenceBrowser(root,{kind:'check',entries,focusPanel:panel,renderFocus({c,left,right,id,number}){
    panel.replaceChildren();panel.dataset.checkId=id;panel.dataset.state=c.state||'unknown';
    const head=el('div',null,'em-head');
    head.append(el('span','证据核对 '+String(number).padStart(2,'0'),'em-kicker'),el('strong',checkNames[c.state]||checkNames.unknown,'em-status'));panel.append(head);
    const fields=[...A(c.conflicts).map(f=>({name:f.field,state:'conflict',left:f.left,right:f.right})),
     ...A(c.matches).map(name=>({name,state:'match'})),...A(c.missing).map(name=>({name,state:'missing'}))];
    function fieldValue(field,side){
     const claim=side==='left'?left:right;
     const value=field.name==='bridge_state'?claim?.[side==='left'?'target_state':'source_state']:claim?.conditions?.[field.name];
     return valueText(valueText(value)==='未说明'?field[side]:value);
    }
    const decisive=fields.find(f=>f.state===({compatible:'match',conflict:'conflict',unknown:'missing'}[c.state]));
    if(decisive){
     const bridge=el('div',null,'em-bridge');
     const label=conditionNames[decisive.name]||decisive.name;
     const endpoint=(prefix,side)=>{const card=el('div',null,'em-bridge-end');card.append(el('small',prefix+' · '+label),el('strong',fieldValue(decisive,side)));return card;};
     const join=el('div',null,'em-join-wrap');
     bridge.append(endpoint('前一条','left'),join,endpoint('后一条','right'));panel.append(bridge);
     const {svg,width}=evidenceDrawing(join,'em-join',30);
     const key='condition-join:'+JSON.stringify([id,decisive,fieldValue(decisive,'left'),fieldValue(decisive,'right')]);
     for(const [i,d]of ['M0 15 H'+width/2,'M'+width+' 15 H'+width/2].entries())once(strokes,{node:S('path',{d},svg),delay:i*55},key+':'+i);
     const symbol=el('span',c.state==='compatible'?'=':c.state==='conflict'?'≠':'?','em-join-symbol');symbol.setAttribute('aria-hidden','true');join.append(symbol);
     once(reveals,{node:symbol,delay:280},key+':result');
    }
    if(fields.length){
     const table=el('table',null,'em-condition-grid'),thead=el('thead'),tr=el('tr'),body=el('tbody');
     for(const text of ['核对项目','前一条证据','后一条证据']){const th=el('th',text);th.scope='col';tr.append(th);}thead.append(tr);table.append(thead,body);
     for(const f of fields){
      const row=el('tr',null,'em-condition-row');row.dataset.state=f.state;
      const status=f.state==='match'?'相符':f.state==='conflict'?'有差异':'缺信息';
      const field=el('th',null);field.scope='row';field.append(el('b',conditionNames[f.name]||f.name),el('span',status,'em-field-status'));
      row.append(field,el('td',fieldValue(f,'left')),el('td',fieldValue(f,'right')));body.append(row);
     }
     panel.append(table);
     once(reveals,{node:body,delay:80},'condition:'+JSON.stringify(c));
    }else panel.append(el('p','此记录只保留了核对结果。','em-source'));
    const detail=el('details',null,'em-detail rc-check-details');detail.dataset.detailKey='check:'+id;detail.append(el('summary','查看两条证据原文'));
    for(const [claim,label]of [[left,'前一条证据'],[right,'后一条证据']]){
     const side=el('div',null,'em-check-source');
     side.append(el('b',label),el('p',papers.get(claim?.paper_id)||papers.get(claim?.passage_id)||'论文标题未记录','em-source'),quoteWithTerms(claim));detail.append(side);
    }
    panel.append(detail);
   }});
   summary('完整显示 '+checks.length+' 项条件检查');return;
  }
  const ds=A(scope().dimensions);
  if(ds.length){
   const heading=el('div',null,'rc-coverage-heading');heading.append(el('strong','各方向的来源覆盖'),el('span','横条表示已记录的论文数量'));root.append(heading);
   const max=Math.max(1,...ds.map(d=>A(d.paper_ids).length)),list=el('div',null,'rc-coverage-list');root.append(list);
   ds.forEach((d,i)=>{
    const ids=A(d.paper_ids),row=action('',()=>inspect(d.label,ids.length?ids.map(id=>data.papers.find(p=>pid(p)===id)?.title||id):['这个方向暂时没有已定位的论文来源。'],'来源覆盖'),'rc-coverage-row');
    const label=el('span',d.label,'rc-coverage-label'),track=el('span',null,'rc-coverage-track'),bar=el('span');bar.style.width=(ids.length/max*100)+'%';track.setAttribute('aria-hidden','true');track.append(bar);row.append(label,track,el('strong',`${ids.length} 篇`));row.setAttribute('aria-label',`${d.label}，${ids.length} 篇来源，查看论文`);list.append(row);once(reveals,{node:bar,delay:Math.min(i,6)*70,grow:true},'coverage:'+JSON.stringify(d));
   });summary(`完整显示 ${ds.length} 个方向的来源覆盖`);return;
  }
  boardEmpty(root,'还没有条件核对结果',data.info.status==='error'?'本阶段暂时中断。已有的论文和原文关系仍可在前面的阶段查看。':'记录形成后，会在这里逐项比较前后证据的研究条件。');
 }
 function generationState(){
  const records=data.records, stored=data.result?.answer?data.result:latest(s=>s.output?.answer);
  const packet=[...records].reverse().find(s=>Array.isArray(s.input?.context?.sources));
  const rounds=records.filter(s=>/回答生成与完整性检查|续写未完成的回答/.test(s.name||''));
  const history=rounds.filter(s=>Number.isInteger(s.output?.segments)&&Number.isInteger(s.output?.characters))
   .map(({output})=>({segments:output.segments,characters:output.characters,complete:output.complete===true}));
  if(stored.answer)return {result:stored,history};
  const saved=[...rounds].reverse().find(s=>Number.isInteger(s.output?.segments))?.output;
  return {history,sources:packet?.input.context.sources,round:rounds.at(-1)?.input?.round,
   segments:saved?.segments??rounds.at(-1)?.input?.saved_segments,characters:saved?.characters,complete:saved?.complete};
 }
 function draftHistory(root,history,folded){
  if(!history.length)return;
  const section=el(folded?'details':'section',null,'rc-draft-history');
  section.append(el(folded?'summary':'h4','每次保存的字符数'));
  if(folded)section.dataset.detailKey='generation-history';
  const maximum=Math.max(1,...history.map(s=>s.characters));
  for(const record of history){
   const row=el('div',null,'rc-round-row'),track=el('div',null,'rc-round-track'),bar=el('i');
   bar.style.width=100*record.characters/maximum+'%';track.setAttribute('aria-hidden','true');track.append(bar);
   row.append(el('span',`已保存 ${record.segments} 段`),track,el('strong',`${record.characters.toLocaleString('zh-CN')} 个字符`));section.append(row);
   if(!folded)once(reveals,{node:bar,delay:90,grow:true},`saved-segment:${record.segments}:${record.characters}`);
  }
  root.append(section);
 }
 function drafting(root,draft){
  if(!draft.sources&&draft.segments==null&&draft.round==null){
   boardEmpty(root,data.info.status==='running'?'正在准备回答':'尚无回答记录','已保存的论文和原句可以在前面的阶段查看。');return;
  }
  const panel=el('section',null,'rc-draft-board');panel.setAttribute('aria-label','回答生成进度');root.append(panel);
  const items=[
   ['准备原文',draft.sources?`${draft.sources.length} 个片段`:'数量未记录','送入本次回答的原文'],
   ['写入正文',draft.segments!=null?`已保存 ${draft.segments} 段输出`:'等待生成记录',draft.characters!=null?`累计 ${draft.characters} 个字符`:draft.round?`第 ${draft.round} 次生成`:''],
   ['检查完整性',draft.complete===true?'已通过检查':draft.complete===false?'需要续写':'等待检查',draft.complete===true?'等待保存最终正文':'']
  ];
  for(const [i,[label,value,note]] of items.entries()){
   const node=el('div',null,'rc-draft-node');node.dataset.ready=String([!!draft.sources,(draft.segments||0)>0,draft.complete!=null][i]);
   node.append(el('span',label,'rc-draft-label'),el('strong',value));if(note)node.append(el('small',note));panel.append(node);
   appear(node,`draft:${i}:${value}:${note}`,i*70);
  }
  if(draft.sources?.length){const list=el('details',null,'rc-draft-inputs');list.dataset.detailKey='draft-inputs';list.append(el('summary',`查看送入生成的 ${draft.sources.length} 个原文片段`));for(const [i,s] of draft.sources.entries())list.append(action(`[${s.source_index??i}] ${s.title||'论文原文'}`,()=>inspect(s.title||'论文原文',[s.text||s.abstract||'此记录未保存原文。'],'送入生成的片段')));root.append(list);}
  draftHistory(root,draft.history,false);summary(items.map(item=>item[1]).join('，'));
 }
 function findCitedBlocks(body){
  const groups=new Map();
  for(const button of body.querySelectorAll('button[data-citation-index]')){
   const block=button.closest('p,li,td,th,blockquote,h2,h3,h4')||button.parentElement;
   if(!groups.has(block))groups.set(block,new Set());
   groups.get(block).add(Number(button.dataset.citationIndex));
  }
  return [...groups].map(([node,refs])=>({node,refs:[...refs]}));
 }
 function citationMap(root,blocks,sources){
  const map=el('section',null,'rc-citation-map');map.setAttribute('aria-label','正文与引用原文对照');
  const header=el('div',null,'rc-map-header'),select=el('select',null,'rc-cited-block');
  const label=el('label','查看引用位置');label.append(select);
  blocks.forEach(({node},i)=>select.add(new Option(`第 ${i+1} 处 · ${node.textContent.trim().slice(0,48)}`,String(i))));
  header.append(el('h4','从正文查到原文'),label);map.append(header);
  const pair=el('div',null,'rc-map-pair'),claim=el('div',null,'rc-map-claim'),link=el('div',null,'rc-map-link'),passage=el('div',null,'rc-map-passage');
  const citeRow=el('div',null,'rc-map-choices'),excerpt=el('p'),quote=el('blockquote'),sourceTitle=el('cite',null,'rc-map-origin'),sourceNumber=el('span');
  const jump=action('在正文中定位',()=>{data.onBrowse?.();const node=blocks[citedBlock].node;node.tabIndex=-1;node.focus({preventScroll:true});node.scrollIntoView({block:'center',behavior:'instant'});},'rc-jump-block');
  claim.append(el('span','正文表述','rc-map-label'),excerpt,citeRow,jump);
  const trace=S('svg',{viewBox:'0 0 68 20','aria-hidden':'true'},link);
  const path=S('path',{d:'M4 10 H64',fill:'none',stroke:'currentColor','stroke-width':1.7},trace);
  S('circle',{cx:4,cy:10,r:3,fill:'currentColor'},trace);S('circle',{cx:64,cy:10,r:3,fill:'currentColor'},trace);
  link.append(el('span','引用'));passage.append(sourceNumber,quote,sourceTitle);
  pair.append(claim,link,passage);map.append(pair);root.prepend(map);
  function choose(blockIndex,sourceIndex,user=false){
   const prev=blocks[citedBlock];prev?.node.classList.remove('rc-linked-block');
   citedBlock=blocks[blockIndex]?blockIndex:0;const block=blocks[citedBlock];
   citedSource=block.refs.includes(sourceIndex)?sourceIndex:block.refs[0];const s=sources[citedSource];
   select.value=String(citedBlock);block.node.classList.add('rc-linked-block');
   excerpt.textContent=block.node.textContent.trim();sourceNumber.className='rc-map-label';sourceNumber.textContent=`引用原文 [${citedSource}]`;sourceTitle.textContent=s.title||'论文原文';quote.textContent=s.text||s.abstract||'此记录未保存原文。';
   if(citeRow.dataset.block!==String(citedBlock)){
    citeRow.dataset.block=citedBlock;citeRow.replaceChildren();
    for(const ref of block.refs){const b=action(`[${ref}]`,()=>{data.onBrowse?.();choose(citedBlock,ref,true);});b.dataset.citationChoice=ref;b.setAttribute('aria-label',`查看此处引用的原文 [${ref}]`);citeRow.append(b);}
   }
   for(const b of citeRow.children)b.setAttribute('aria-pressed',String(Number(b.dataset.citationChoice)===citedSource));
   if(user&&allowed()&&visible&&!document.hidden){
    for(const a of [path,passage].flatMap(n=>n.getAnimations()))a.cancel();
    animations=animations.filter(a=>a.playState!=='finished'&&a.playState!=='idle');
    animations.push(path.animate([{strokeDasharray:'60 60',strokeDashoffset:60},{strokeDasharray:'60 60',strokeDashoffset:0}],{duration:340,easing:'ease-out'}),passage.animate([{opacity:.55},{opacity:1}],{duration:240}));syncPause();
   }
  }
  select.onchange=()=>{data.onBrowse?.();choose(Number(select.value),null,true);};
  choose(citedBlock,citedSource);once(strokes,{node:path,delay:100},'answer-citation-trace');appear(passage,'answer-first-source',210);return choose;
 }
 function generation(){
  const draft=generationState(),root=board();root.classList.add('rc-generation-board');
  if(!draft.result){drafting(root,draft);return;}
  const result=draft.result,sources=A(result.sources),article=el('section',null,'rc-generated-answer');article.append(el('div','回答正文','rc-column-label'));
  const body=el('article',null,'rc-answer-reading markdown-body');body.dataset.scrollKey='answer';body.setAttribute('role','region');body.setAttribute('aria-label','完整回答正文');body.tabIndex=0;
  let blocks=[],chooseReference=null;
  function inspectSource(i,_,trigger){
   const source=sources[i];if(!source)return;
   if(chooseReference){
    const owner=trigger?.closest('p,li,td,th,blockquote,h2,h3,h4')||trigger?.parentElement;
    const at=blocks.findIndex(b=>owner?b.node===owner:b.refs.includes(i));if(at>=0)chooseReference(at,i);
   }
   for(const item of root.querySelectorAll('[data-source-index]'))item.classList.toggle('rc-source-current',Number(item.dataset.sourceIndex)===i);
   inspect(source.title||'论文来源',[source.text||source.abstract||'此记录未保存原文。'],`引用 [${i}]`);
  }
  if(window.researchReader){const sections=researchReader.sections(result);researchReader.render(body,sections.body,{sources,onCitation:inspectSource});}else body.append(el('p',result.answer));
  article.append(body);root.append(article);appear(article,'answer-ready');
  blocks=findCitedBlocks(body);if(blocks.length)chooseReference=citationMap(root,blocks,sources);
  const referenced=new Set(blocks.flatMap(block=>block.refs));
  const evidence=el('section',null,'rc-answer-sources');evidence.append(el('div',`来源 · ${unique(sources).length} 篇论文`,'rc-column-label'));
  const list=el('div',null,'rc-complete-papers');list.dataset.scrollKey='answer-sources';list.setAttribute('role','region');list.setAttribute('aria-label','全部回答来源');list.tabIndex=0;
  sources.forEach((p,i)=>{const item=card(p,i,referenced.has(i)?'正文已引用':'输入的原文片段',`answer-source:${i}:${pid(p)}`);item.dataset.sourceIndex=i;item.querySelector('.rc-document-number').textContent=`[${i}]`;item.setAttribute('aria-label',`引用 [${i}]：${p.title||'论文来源'}`);item.onclick=()=>inspectSource(i);list.append(item);});
  if(!sources.length)list.append(el('p','这份记录未保存来源。','rc-board-empty'));evidence.append(list);root.append(evidence);
  draftHistory(root,draft.history,true);summary(`完整回答正文与 ${sources.length} 个来源片段，点击引用核对原文`);
 }
 function allowed(){return document.documentElement.dataset.motion!=='off'&&!matchMedia('(prefers-reduced-motion:reduce)').matches;}
 function cancel(){animations.forEach(a=>a.cancel());animations=[];}
 function animate(){
  cancel();
  if(!allowed()){settled=Promise.resolve();return settled;}
  // Read each scroll window once, before starting animations. All other rows
  // stay fully visible to scrolling, keyboard navigation and browser find.
  const visibleRows=new Set();
  for(const list of stage.querySelectorAll('.rc-complete-papers,.rc-relations-list,.rc-check-list')){
   const rect=list.getBoundingClientRect(),top=Math.max(0,rect.top),bottom=Math.min(innerHeight,rect.bottom);
   if(top>=bottom)continue;
   let count=0;
   for(const row of list.children){
    const bounds=row.getBoundingClientRect();
    if(bounds.top>=bottom)break;
    if(bounds.bottom>top){visibleRows.add(row);if(++count===8)break;}
   }
  }
  function visibleItem({node}){
   const row=node.closest('.rc-full-paper,.rc-relation-card,.rc-check-item');
   return !row||visibleRows.has(row);
  }
  for(const {node,delay} of strokes.filter(visibleItem)){
   const length=node.getTotalLength();
   if(!length)continue;
   animations.push(node.animate([{strokeDasharray:`${length} ${length}`,strokeDashoffset:length},{strokeDasharray:`${length} ${length}`,strokeDashoffset:0}],{duration:500,delay,fill:'backwards',easing:'ease-out'}));
  }
  for(const {node,delay,grow} of reveals.filter(visibleItem)){
   animations.push(node.animate(grow?[{transform:'scaleX(0)'},{transform:'scaleX(1)'}]:[{opacity:.2},{opacity:1}],{duration:grow?500:280,delay,fill:'backwards',easing:'ease-out'}));
  }
  for(const {node,delay} of htmlMoves.filter(visibleItem)){
   animations.push(node.animate([{transform:'translateY(7px)',opacity:.18},{transform:'none',opacity:1}],{duration:280,delay,fill:'backwards',easing:'ease-out'}));
  }
  for(const {node,delay} of retrievalCues){
   animations.push(node.animate([{opacity:.5},{opacity:1}],{duration:240,delay,easing:'ease-out'}));
  }
  syncPause();settled=Promise.allSettled(animations.map(a=>a.finished));return settled;
 }
 function syncPause(){for(const a of animations){if(a.playState==='finished'||a.playState==='idle')continue;if(paused||!visible||document.hidden||host.closest('[hidden]'))a.pause();else a.play();}}
 function update(next){data=next;
  const changedRun=sceneRun!==next.run.id,changedPhase=scenePhase!==next.phase;
  if(changedRun){citedBlock=0;citedSource=null;seenVisuals.clear();scrollPositions.clear();openDetails.clear();relationPaper='all';relationType='all';seenItems.clear();selectedDirection='all';filterDestination='selected';sceneRun=next.run.id;scenePhase=-1;}
  if(next.phase===1&&next.following&&(next.run.status==='running'||next.searchId)){
   const requests=searches().filter(s=>!s.output?.retry_scheduled&&!/连接重试/.test(s.name||''));
   const current=requests.find(s=>s.id===next.searchId)||requests.reduce((last,s)=>(s.seq||0)>(last?.seq||-1)?s:last,null);
   if(current){const direction=searchDirections(requests).find(d=>belongsToDirection(current,d));selectedDirection=direction?.id||'all';}
  }
  const paperLabels=()=>[...evidencePapers()];
  const contentKeys=[
   ()=>[next.run.question,plan()],
   ()=>[searches().map(s=>[s.id,s.status,s.input,s.output?.papers]),plan(),selectedDirection],
   ()=>[searches().map(s=>s.output?.papers),selection(),filterDestination],
   ()=>[[...next.claims.values()],next.labels,paperLabels(),relationPaper,relationType],
   ()=>[latest(s=>/路径、条件/.test(s.name||'')),next.result?.candidate_paths,next.result?.paths,next.result?.rejected_links,scope(),[...next.claims.values()],next.labels,paperLabels()],
   generationState
  ];
  const nextKey=JSON.stringify([next.run.id,next.phase,next.info.status,contentKeys[next.phase]()]);if(nextKey===key)return settled;
  if(!changedRun){for(const n of stage.querySelectorAll('[data-scroll-key]'))scrollPositions.set(n.dataset.scrollKey,n.scrollTop);
   for(const detail of stage.querySelectorAll('[data-detail-key]')){if(detail.open)openDetails.add(detail.dataset.detailKey);else openDetails.delete(detail.dataset.detailKey);}}
  const active=document.activeElement;
  const focus=stage.contains(active)?['claimId','checkId','evidenceFilter','citationChoice','paperLocator','sourceIndex','paperId','direction','scrollKey','batchId'].find(k=>active.dataset[k]!==undefined):null;
  const focusList=focus==='paperId'?active.closest('[data-scroll-key]')?.dataset.scrollKey:undefined;
  scenePhase=next.phase;key=nextKey;
  cancel();strokes=[];reveals=[];htmlMoves=[];retrievalCues=[];if(changedRun||changedPhase)q('.rc-inspector').hidden=true;stage.replaceChildren();stage.removeAttribute('aria-description');stage.classList.remove('rc-stage-board');q('.rc-title').textContent=titles[next.phase];
  q('.rc-heading .rc-eyebrow').textContent=`第 ${next.phase+1} 步 / 共 ${titles.length} 步`;
  const state=q('.rc-scene-state');state.dataset.state=next.info.status;state.textContent=({running:'正在更新',done:'已记录',error:'暂时中断',stopped:'已停止',waiting:'等待结果'})[next.info.status]||'已记录';
  [planning,retrieval,filtering,relationships,checking,generation][next.phase]();
  for(const detail of stage.querySelectorAll('[data-detail-key]'))detail.open=openDetails.has(detail.dataset.detailKey);
  for(const list of stage.querySelectorAll('[data-scroll-key]'))list.scrollTop=scrollPositions.get(list.dataset.scrollKey)||0;
  if(!changedPhase&&!changedRun){
   const target=focus?[...stage.querySelectorAll('button,select,[data-scroll-key]')].find(n=>n.dataset[focus]===active.dataset[focus]&&
    (focus!=='paperId'||n.closest('[data-scroll-key]')?.dataset.scrollKey===focusList)):
    active.matches('.rc-cited-block')?stage.querySelector('.rc-cited-block'):null;
   target?.focus({preventScroll:true});
  }
  alignRetrievalLink();return animate();
 }
 function closeInspector(){q('.rc-inspector').hidden=true;if(inspectorTrigger?.isConnected)inspectorTrigger.focus({preventScroll:true});}
 q('.rc-close').onclick=closeInspector;
 host.addEventListener('keydown',e=>{if(e.key==='Escape'&&!q('.rc-inspector').hidden){closeInspector();e.stopPropagation();}});
 const linkLayoutObserver=new ResizeObserver(()=>{alignRetrievalLink();});linkLayoutObserver.observe(stage);
 stage.addEventListener('toggle',event=>{if(event.target.matches('.rc-plan-board details'))alignPlanLinks();},true);
 const observer=new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;syncPause();});observer.observe(host);
 document.addEventListener('visibilitychange',syncPause);document.addEventListener('clink-preferences',()=>{if(!allowed())cancel();else syncPause();});
 matchMedia('(prefers-reduced-motion:reduce)').addEventListener('change',()=>{if(!allowed())cancel();});
 return {update,finished:()=>settled,stop:cancel};
};

/* Readable research narrative, derived exclusively from recorded events. */
window.createResearchJourney = function(host) {
 const E=(tag,text,cls)=>{const n=document.createElement(tag);if(text!=null)n.textContent=text;if(cls)n.className=cls;return n;};
 const arr=v=>Array.isArray(v)?v:[];
 const cross=p=>new Set(arr(p.paper_ids)).size>1;
 const single=p=>arr(p.relations||p.claim_ids).length===1;
 const uniquePapers=ps=>new Set(ps.map(p=>p.paperId||p.paper_id||p.id||p.title)).size;
 const phases=[['理解你的问题','明确问题与资料范围'],['寻找相关论文','看实际使用的检索词'],['挑选阅读材料','了解哪些材料被留下'],['连接论文证据','从原句走到解释链'],['核对证据条件','比较研究条件与来源覆盖'],['形成有据回答','回到来源检查结论']];
 let state={},selected=null,following=true,lastKey='',lastId='';
 let incoming=null,incomingKey='',wasLive=false,queue=[],queueEpoch=0,draining=false;
 host.className='research-story';
 host.innerHTML=`<div class="story-heading"><div><h2>从问题到答案</h2><p id="story-status" role="status"></p></div><div class="story-playback"><button id="story-follow" class="secondary" type="button">跟随最新进展</button></div></div>
  <section class="story-map" aria-label="研究过程总览"><nav id="story-route" aria-label="研究路线"></nav></section>
  <details id="story-scope-panel" class="story-scope-panel" hidden><summary id="story-scope-summary">本次证据范围</summary><div id="story-scope" class="story-scope" aria-label="本次证据范围"></div></details>
  <div class="story-layout"><section class="story-main panel"><div id="story-scene"></div><div class="story-nav"><button id="story-prev" class="secondary">← 上一阶段</button><button id="story-next" class="secondary">下一阶段 →</button></div>
  <details id="story-technical"><summary>查看这一阶段的技术记录</summary><div id="story-records"></div></details></section></div>`;
 const $s=id=>host.querySelector('#'+id);
 const visualScene=window.createResearchScene($s('story-scene'));
 host.dataset.presentation='canvas';
 function phase(s){const n=s.name||'';
  if(n.startsWith('结构化输出')){const parent=state.steps?.get(s.parent);if(parent&&parent.id!==s.id)return phase(parent);}
  if(/查询规划|加载运行环境|运行模型配置|固定科学论文语料/.test(n))return 0;
  if(/路径、条件|冲突分析|范围与证据覆盖/.test(n))return 4;
  if(/路径证据包生成|回答生成|续写未完成|保存回答|初始回答|反思|引用|合成|输出回答|汇总/.test(n))return 5;
  if(/构建或加载|实体与关系|路径/.test(n))return 3;
  if(/重排|排序|筛选|种子召回/.test(n)||s.kind==='gpu')return 2;
  if(/检索|召回|扩展|缺口/.test(n)||s.kind==='http')return 1;
  return 0;
 }
 function records(){const all=[...(state.steps?.values()||[])],resume=all.filter(s=>s.name==='继续研究 · 恢复已保存的进度').at(-1)?.seq||0;return all.filter(s=>s.kind!=='llm'&&!/跨文献检索与生成$/.test(s.name||'')&&!(s.seq<resume&&['error','interrupted','cancelled'].includes(s.status)));}
 function group(i){return records().filter(s=>phase(s)===i||(i===3&&/路径、条件/.test(s.name||'')));}
 function latest(){const rs=records();return [...rs].reverse().find(s=>!s.status)||rs.at(-1);}
 function latestOut(test){return [...records()].reverse().find(s=>test(s))?.output||{};}
 function note(text,cls='story-note'){return E('p',text,cls);}
 function button(text,fn,cls='text-button'){const b=E('button',text,cls);b.type='button';b.onclick=fn;return b;}
 function choose(i){const position=window.scrollY;stopFollowing();if(incoming)state={...incoming,displayPhase:undefined};selected=i;render(true);window.scrollTo({top:position,behavior:'instant'});}
 function allPapers(){const seen=new Map();for(const s of records()){const o=s.output||{};for(const p of [...arr(o.papers),...arr(o.selected_papers),...arr(o.usable_contexts),...arr(o.candidates),...arr(o.ranked),...arr(o.sources),...arr(s.input?.context?.sources)]){if(!p||!p.title)continue;const id=p.paperId||p.paper_id||p.id||p.title;seen.set(id,{...seen.get(id),...p});}}for(const p of arr(state.result?.sources)){const id=p.id||p.paper_id||p.title;seen.set(id,{...seen.get(id),...p});}return [...seen.values()];}
 function sourcesAndClaims(){
  const claims=new Map(),result=state.result||{},labels={...result.entity_labels};
  for(const s of records()){
   Object.assign(labels,s.input?.entity_labels||{});
   for(const c of [...arr(s.output?.claims),...arr(s.input?.candidate_claims)])if(c?.id)claims.set(c.id,c);
   for(const e of arr(s.output?.entities))labels[e.id]=e.name;
  }
  const paths=new Map(arr(result.candidate_paths).filter(p=>p.id).map(p=>[p.id,p]));
  const passagePapers=new Map(arr(result.sources).filter(s=>s.passage_id).map(s=>[s.passage_id,s.paper_id||s.id]));
  for(const path of arr(result.paths)){
   const candidate=paths.get(path.id);
   for(const [index,relation] of arr(path.relations).entries()){
    if(!relation?.source||!relation.target)continue;
    const id=relation.id||candidate?.claim_ids?.[index]||path.checks?.[index]?.left||path.checks?.[index-1]?.right||
     JSON.stringify([relation.paper_id,relation.passage_id,relation.source,relation.target,relation.type,relation.quote]);
    const paper=relation.paper_id||passagePapers.get(relation.passage_id)||(path.paper_ids?.length===1?path.paper_ids[0]:undefined);
    if(!claims.has(id))claims.set(id,{...relation,id,paper_id:paper});
   }
  }
  return {claims,labels};
 }
 function renderScope(){const r=state.result||{},selected=latestOut(s=>s.output?.selected_papers),request=records().find(s=>/摘要筛选与/.test(s.name||''))?.input||{},sources=arr(r.sources),box=$s('story-scope');box.replaceChildren();$s('story-scope-panel').hidden=!sources.length&&!selected.selected_papers;if($s('story-scope-panel').hidden)return;const indexed=r.corpus_stats?.indexed??selected.selected_papers?.length??'—',candidates=r.corpus_stats?.candidates??request.candidates??'—',used=r.sources?uniquePapers(sources):'—';$s('story-scope-summary').textContent=`证据范围：${indexed} 篇进入分析 · ${used} 篇用于回答 · 查看覆盖详情`;box.append(E('strong','这次研究实际用了多少证据'),note(`${candidates} 篇候选 → ${indexed} 篇进入分析 → ${used} 篇用于回答`));if(r.sources){const paths=arr(r.paths);box.append(note(`${sources.length} 个原文片段；${paths.filter(single).length} 条单关系记录；${paths.filter(cross).length} 条跨论文链。`,'fine'));}const scope=r.evidence_scope||latestOut(s=>s.output?.unique_papers!==undefined&&s.output?.dimensions);if(scope.dimensions){const list=E('div',null,'coverage-grid');for(const d of scope.dimensions){const card=E('div');card.append(E('strong',d.label),E('span',`${d.paper_ids.length} 篇含定位原句的来源`),E('small',!d.paper_ids.length?'当前回答缺少该维度依据':d.paper_ids.length===1?'单篇来源':'多篇来源'));list.append(card);}box.append(list);}else if(r.sources)box.append(note('这份记录未保存维度覆盖分析。','fine'));}
 function phaseSummaries(rs,claims){
  const result=state.result||{},plan=result.research_plan||latestOut(s=>s.output?.plan).plan;
  const searches=rs.filter(s=>s.kind==='http'&&s.input?.query);
  const recordedPapers=searches.flatMap(s=>arr(s.output?.papers));
  const returned=searches.some(s=>Array.isArray(s.output?.papers));
  const count=rs.find(s=>/摘要筛选与/.test(s.name||''))?.input?.candidates??latestOut(s=>s.output?.unique_candidates!==undefined).unique_candidates??(returned?uniquePapers(recordedPapers):undefined);
  const selectedPapers=latestOut(s=>s.output?.selected_papers).selected_papers;
  const read=rs.filter(s=>/论文实体与关系/.test(s.name||'')&&s.status==='success').length;
  const analysis=latestOut(s=>/路径、条件/.test(s.name||'')),paths=arr(result.candidate_paths||analysis.paths||result.paths);
  const checks=paths.reduce((sum,path)=>sum+arr(path.checks).length,0)+arr(result.rejected_links||analysis.rejected_links).length;
  const generated=latestOut(s=>s.output?.answer),sources=result.sources||generated.sources;
  const coverage=arr((result.evidence_scope||latestOut(s=>s.output?.unique_papers!==undefined&&s.output?.dimensions)).dimensions).length;
  const recorded=[Boolean(plan),returned,Array.isArray(selectedPapers),claims.size>0,checks>0||coverage>0,Boolean(result.answer||generated.answer)];
  const metrics=[plan?`${arr(plan.dimensions).length} 个研究方向`:'等待研究方向', count!==undefined?`${count} 篇候选论文`:'等待检索结果',
   selectedPapers?`${selectedPapers.length} 篇进入分析`:'等待筛选结果',claims.size?`${claims.size} 条原文关系`:read?`${read} 篇已阅读`:'等待原文关系',
   checks?`${checks} 项条件核对`:coverage?`${coverage} 个方向的来源覆盖`:'暂无逐项核对',sources?`${uniquePapers(arr(sources))} 篇回答来源`:'等待回答生成'];
  return metrics.map((metric,i)=>{
   const events=rs.filter(s=>phase(s)===i||(i===3&&/路径、条件/.test(s.name||'')));
   let status='waiting';
   if(events.some(s=>s.status==='error'))status='error';
   else if(state.run.status==='running'&&events.some(s=>!s.status||s.status==='running'))status='running';
   else if(events.some(s=>s.status==='success')||recorded[i])status='done';
   else if(events.length)status='stopped';
   if(status==='waiting')metric='尚无记录';
   else if(i===4&&!checks&&!coverage&&status!=='done')metric='等待核对结果';
   return {status,metric};
  });
 }
 const phaseIcons=[
  '<path d="M5 4h14v12H9l-4 4V4Z"/><path d="M9 8h6m-6 4h4"/>',
  '<circle cx="10" cy="10" r="6"/><path d="m15 15 5 5"/>',
  '<path d="M5 4h14v16H5zM8 8h8M8 12h4m1 4 2 2 4-4"/>',
  '<circle cx="5" cy="12" r="3"/><circle cx="18" cy="5" r="3"/><circle cx="18" cy="19" r="3"/><path d="m8 10 7-4M8 14l7 4"/>',
  '<path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3Z"/><path d="m8 12 3 3 5-6"/>',
  '<path d="M5 3h10l4 4v14H5V3Zm10 0v5h4M9 12h6m-6 4h6"/>'
 ];
 const route=$s('story-route');
 const routeSteps=phases.map(([name],i)=>{
  const b=button('',()=>choose(i),'story-route-step');
  const icon=E('span',null,'story-route-index');icon.innerHTML=`<svg viewBox="0 0 24 24" aria-hidden="true">${phaseIcons[i]}</svg>`;
  b.onkeydown=e=>{
   const target=({ArrowRight:Math.min(5,i+1),ArrowLeft:Math.max(0,i-1),Home:0,End:5})[e.key];
   if(target===undefined||e.altKey||e.ctrlKey||e.metaKey)return;
   e.preventDefault();choose(target);routeSteps[target].b.focus({preventScroll:true});
  };
  const words=E('div'),metric=E('span',null,'story-route-result');
  words.append(E('strong',name),metric);b.append(icon,words);route.append(b);
  return {b,metric};
 });
 function render(force=false){
  if(!state.run?.id)return;
  const current=latest(),active=state.displayPhase??(state.run.status==='success'&&state.result?.answer?5:current?phase(current):0);
  const i=following?active:(selected??active),running=state.run.status==='running',rs=records();selected=i;
  // receive() compares content before rendering. A stable frame also retains a
  // keyboard user's focused stage when unrelated records arrive.
  if(!force&&lastKey===state)return;
  lastKey=state;
  $s('story-status').textContent=draining?`正在呈现：${phases[i][0]}`:
   running?`正在${phases[active][0]} · 新结果会自动出现`:`${statusNames[state.run.status]||'研究记录'} · 点击阶段查看结果`;
  $s('story-follow').textContent=following?'已跟随最新进展':'跟随最新进展';
  $s('story-follow').disabled=following;$s('story-follow').hidden=!running;
  const {claims,labels}=sourcesAndClaims(),infos=phaseSummaries(rs,claims);
  const statusText={running:'进行中',done:'已记录',error:'需处理',stopped:'已中断',waiting:'待开始'};
  routeSteps.forEach(({b,metric},n)=>{
   const info=infos[n];b.dataset.selected=String(n===i);b.dataset.state=info.status;
   b.setAttribute('aria-current',n===i?'step':'false');
   b.setAttribute('aria-label',`第 ${n+1} 步，${phases[n][0]}，${info.metric}，${statusText[info.status]}`);
   if(metric.textContent!==info.metric)metric.textContent=info.metric;
  });
  renderScope();
  visualScene.update({run:state.run,result:state.result||{},phase:i,following,searchId:state.displaySearchId,info:infos[i],records:rs,papers:allPapers(),claims,labels,onInspect:stopFollowing,onBrowse:stopFollowing});
  if($s('story-technical').open)renderLogs();
  $s('story-prev').disabled=i===0;$s('story-next').disabled=i===5;
 }
 function renderLogs(){
  const logs=$s('story-records');logs.replaceChildren();
  group(selected).forEach(s=>logs.append(button(`${s.status==='success'?'已完成':s.status?'未完成':'已开始'} · ${s.name}`,()=>{switchTab(false);pick(s.id);},'story-log')));
  if(!logs.childNodes.length)logs.append(note('这一阶段尚无独立步骤记录。'));
 }
 $s('story-technical').ontoggle=()=>{if($s('story-technical').open)renderLogs();};
 $s('story-prev').onclick=()=>choose(Math.max(0,selected-1));$s('story-next').onclick=()=>choose(Math.min(5,selected+1));
 $s('story-follow').onclick=()=>{clearQueue();following=true;if(incoming)state={...incoming,displayPhase:undefined};render(true);};
 function clearQueue(){queueEpoch++;queue=[];draining=false;visualScene.stop();}
 function stopFollowing(){clearQueue();following=false;$s('story-follow').hidden=state.run?.status!=='running';$s('story-follow').disabled=false;$s('story-follow').textContent='跟随最新进展';}
 function visibleJourney(){return !host.closest('[hidden]')&&!document.hidden;}
 async function drain(){
  if(draining||!following||!visibleJourney()||!queue.length)return;
  draining=true;const epoch=queueEpoch;
  try{while(queue.length&&following&&visibleJourney()&&epoch===queueEpoch){state=queue.shift();lastKey='';render(true);await visualScene.finished();}}
  finally{if(epoch===queueEpoch){draining=false;if(!queue.length&&state.run){$s('story-status').textContent=state.run.status==='running'?`正在${phases[selected??0][0]} · 等待新结果`:`${statusNames[state.run.status]||'研究记录'} · 点击阶段查看完整结果`;}}}
 }
 function enqueue(frame){
  const last=queue.at(-1);
  if(last&&last.displayPhase===frame.displayPhase&&last.displaySearchId===frame.displaySearchId&&last.draftStep===frame.draftStep)queue[queue.length-1]=frame;
  else queue.push(frame);
 }
 function receive(s){
  if(!s.run?.id)return;
  // The API cursor advances on every recorded change. On idle live polls the
  // entire library of abstracts and model transcripts can stay untouched.
  const versioned=Number.isSafeInteger(s.traceCursor);
  const signature=versioned?JSON.stringify([s.run.id,s.run.status,s.run.question,s.traceCursor,s.result]):
   JSON.stringify([s.run.id,s.run.status,s.run.question,s.result,[...(s.steps?.values()||[])].map(x=>[x.id,x.seq,x.status,x.input,x.output])]);
  if(signature===incomingKey){drain();return;}incomingKey=signature;
  const previous=incoming,sameRun=previous?.run?.id===s.run.id,old=sameRun?previous.steps:new Map();
  const steps=new Map(),changed=[];
  for(const [id,event] of s.steps||[]){
   const before=old.get(id);
   if(before&&before.seq===event.seq&&before.status===event.status&&
    (versioned||(JSON.stringify(before.output)===JSON.stringify(event.output)&&JSON.stringify(before.input)===JSON.stringify(event.input)))){
    steps.set(id,before);continue;
   }
   const snapshot=structuredClone(event);steps.set(id,snapshot);changed.push(snapshot);
  }
  const copy={run:structuredClone(s.run),result:s.result?structuredClone(s.result):null,steps};incoming=copy;
  if(lastId!==s.run.id){clearQueue();lastId=s.run.id;following=true;selected=null;lastKey='';wasLive=false;state=copy;}
  const live=wasLive||s.run.status==='running';wasLive=live;
  if(!live||!following){state=copy;if(!host.hidden)render();return;}
  const working=new Map(old);changed.sort((a,b)=>(a.seq||0)-(b.seq||0));
  for(const step of changed){working.set(step.id,step);if(step.kind==='llm'||/跨文献检索与生成$|结构化输出/.test(step.name||''))continue;
   const n=phase(step);
   const search=n===1?[...working.values()].filter(s=>s.kind==='http'&&s.input?.query&&!s.output?.retry_scheduled&&!/连接重试/.test(s.name||'')).reduce((last,s)=>(s.seq||0)>(last?.seq||-1)?s:last,null):null;
   const draftStep=n===5&&/回答生成与完整性检查|续写未完成的回答/.test(step.name||'')?step.id:undefined;
   enqueue({...copy,steps:new Map(working),result:null,displayPhase:n,displaySearchId:search?.id,draftStep});
  }
  if(copy.result?.answer&&copy.run.status==='success')enqueue({...copy,displayPhase:5,draftStep:'final'});
  else if(previous?.run?.status!==copy.run.status)enqueue({...copy,displayPhase:queue.at(-1)?.displayPhase??selected??0,displaySearchId:queue.at(-1)?.displaySearchId??state.displaySearchId});
  if(!queue.length&&!draining){state=copy;if(!host.hidden)render();}else drain();
 }
 const queueVisibility=new MutationObserver(()=>{if(visibleJourney())drain();});
 queueVisibility.observe(document.body,{attributes:true,subtree:true,attributeFilter:['hidden','data-screen']});
 document.addEventListener('visibilitychange',()=>{if(!document.hidden)drain();});
 return {update:receive,render:()=>{if(!draining&&!queue.length)render();drain();},reset:()=>{clearQueue();lastKey='';incomingKey='';}};
};
