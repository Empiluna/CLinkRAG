/* Data-backed animated research scenes. Nodes always refer to recorded objects. */
window.createResearchScene=function(host){
 const NS='http://www.w3.org/2000/svg',A=v=>Array.isArray(v)?v:[],pid=p=>p?.paperId||p?.paper_id||p?.id||p?.title;
 const titles=['这项研究要查哪些问题','各个方向找到了哪些论文','哪些论文进入了分析','论文之间有哪些共同发现','这些发现能否放在一起比较','研究回答用了哪些原文'];
 let data=null,key='',animations=[],paused=false,visible=true,strokes=[],reveals=[],htmlMoves=[],selectedDirection='all',filterDestination='selected',sceneRun='',scenePhase=-1,seenItems=new Set(),settled=Promise.resolve(),retrievalCues=[];
 let relationPaper='all',relationType='all',inspectorTrigger=null;
 const animatedRelations=new Set(),seenVisuals=new Set(),scrollPositions=new Map(),openDetails=new Set();
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
 function dimensions(){return A((data.result?.research_plan||latest(s=>s.output?.plan).plan)?.dimensions);}
 function searches(){return data.records.filter(s=>s.kind==='http'&&s.input?.query);}
 function selection(){return latest(s=>s.output?.selected_papers);}
 function scope(){return data.result?.evidence_scope||latest(s=>s.output?.unique_papers!==undefined&&s.output?.dimensions);}
 function summary(textValue){stage.setAttribute('aria-description',textValue);}
 function planning(){
  const ds=dimensions(),root=board();root.classList.add('rc-plan-board');summary(`${ds.length} 个研究方向`);
  const question=el('article',null,'rc-plan-question');question.append(el('span','你提出的问题','rc-column-label'),el('h4',data.run.question),el('p',ds.length?`从问题展开 ${ds.length} 个检索方向`:'研究方向会随规划结果出现'));root.append(question);appear(question,'question:'+data.run.question);
  const branches=el('div',null,'rc-plan-branches');root.append(branches);
  for(const [i,d]of ds.entries()){
   const branch=el('article',null,'rc-plan-branch'),number=el('span',String(i+1).padStart(2,'0'),'rc-branch-number'),content=el('div',null,'rc-branch-content');
   const link=S('svg',{viewBox:'0 0 33 2','aria-hidden':'true',class:'rc-branch-link'},branch),line=S('path',{d:'M0 1H33'},link);once(strokes,{node:line,delay:80+i*80},'plan-link:'+d.id);
   content.append(el('h4',d.label));const detail=el('details',null,'rc-query-detail');detail.dataset.detailKey='direction:'+d.id;detail.append(el('summary','查看实际检索词'));
   if(d.query)detail.append(el('p',d.query));if(d.followup_query)detail.append(el('p','补充检索：'+d.followup_query));if(!d.query&&!d.followup_query)detail.append(el('p','检索词尚未记录。'));content.append(detail);branch.append(number,content);branches.append(branch);appear(content,'direction:'+JSON.stringify(d),160+i*80);appear(number,'direction-number:'+d.id,160+i*80);
  }
  if(!ds.length)boardEmpty(branches,data.info.status==='error'?'问题规划暂时中断':'正在展开研究方向',data.info.status==='error'?'已保存的问题仍可保留；继续研究后会从记录接着进行。':'方向和检索词确定后，会完整展示在这里。');
 }
 function belongsToDirection(search,d){return search.input?.dimension===d.id||search.input?.query===d.query||search.input?.query===d.followup_query;}
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
  const connector=el('div',null,'rc-results-connector');connector.append(el('span','检索结果'));
  const arrow=S('svg',{viewBox:'0 0 88 26','aria-hidden':'true'},connector);
  const line=S('path',{d:'M3 13H79M70 5L79 13L70 21',class:'rc-result-arrow'},arrow);
  once(strokes,{node:line,delay:80},'retrieval-link:'+selectedDirection);parent.append(connector);
 }
 function alignRetrievalLink(){
  const connector=stage.querySelector('.rc-results-connector'),active=stage.querySelector('.rc-direction-button[aria-pressed=true]'),heading=stage.querySelector('.rc-found-heading');
  if(!connector||!active||!heading||matchMedia('(max-width:760px)').matches)return;
  const r=connector.getBoundingClientRect(),a=active.getBoundingClientRect(),h=heading.getBoundingClientRect();if(!r.width||!r.height)return;
  const y1=a.top+a.height/2-r.top,y2=h.top+h.height/2-r.top,x2=r.width-8,mid=r.width/2;
  connector.querySelector('svg').setAttribute('viewBox',`0 0 ${r.width} ${r.height}`);
  connector.querySelector('path').setAttribute('d',`M5 ${y1} C${mid} ${y1} ${mid} ${y2} ${x2} ${y2} M${x2-7} ${y2-6} L${x2} ${y2} L${x2-7} ${y2+6}`);
  connector.querySelector('span').style.top=Math.max(0,y2-30)+'px';
 }
 function retrieval(){
  const root=board(),ds=dimensions(),ss=searches(),all=unique(ss.flatMap(s=>A(s.output?.papers)));
  root.classList.add('rc-retrieval-board');
  if(selectedDirection!=='all'&&!ds.some(d=>d.id===selectedDirection))selectedDirection='all';
  const nav=el('nav',null,'rc-direction-list');nav.setAttribute('aria-label','选择检索方向');
  nav.append(el('div','检索方向','rc-column-label'));
  const options=[{id:'all',label:'全部方向'},...ds];
  const byDirection=new Map(ds.map(d=>{const queries=ss.filter(s=>belongsToDirection(s,d));return [d.id,{queries,papers:unique(queries.flatMap(s=>A(s.output?.papers)))}];}));
  byDirection.set('all',{queries:ss,papers:all});
  options.forEach(d=>{const {queries,papers:found}=byDirection.get(d.id);
   const searching=data.run.status==='running'&&queries.some(s=>!s.status||s.status==='running');
   const label=searching?(found.length?`正在补充搜索 · 已找到 ${found.length} 篇`:'正在搜索…'):found.length?`${found.length} 篇论文`:queries.some(s=>s.status==='error')?'检索未完成':queries.some(s=>s.status==='success')?'未找到论文':'等待检索结果';
   const b=action('',()=>browse(()=>{selectedDirection=d.id;}),'rc-direction-button');b.dataset.direction=d.id;b.setAttribute('aria-pressed',String(selectedDirection===d.id));b.append(el('strong',d.label),el('span',label));nav.append(b);
  });root.append(nav);channel(root);
  const direction=ds.find(d=>d.id===selectedDirection),{papers,queries:currentQueries}=byDirection.get(selectedDirection);
  const origins=new Map();for(const d of ds)for(const p of byDirection.get(d.id).papers){const names=origins.get(pid(p))||[];names.push(d.label);origins.set(pid(p),names);}
  const col=paperColumn(root,papers,direction?direction.label:'全部候选论文','retrieval:'+selectedDirection,p=>{const names=origins.get(pid(p));return names?.length?'来自：'+names.join('、'):'';});
  const heading=col.querySelector('.rc-column-heading');heading.classList.add('rc-found-heading');
  const searching=data.run.status==='running'&&currentQueries.some(s=>!s.status||s.status==='running');
  heading.setAttribute('aria-live','polite');
  heading.replaceChildren(el('span',direction?direction.label:'全部方向 · 合并重复论文'),el('strong',searching?(papers.length?`正在补充搜索 · 已找到 ${papers.length} 篇论文`:'正在搜索相关论文…'):papers.length?`找到 ${papers.length} 篇论文`:data.info.status==='error'?'检索未完成':currentQueries.some(s=>s.status==='success')?'未找到论文':'等待检索结果'));
  const batches=currentQueries.filter(s=>A(s.output?.papers).length);
  if(data.following&&data.run.status==='running'&&batches.length>1){
   const previous=new Set(batches.slice(0,-1).flatMap(s=>s.output.papers.map(pid)));
   const added=unique(batches.at(-1).output.papers).filter(p=>!previous.has(pid(p))).length;
   const change=el('small',added?`本批新增 ${added} 篇`:'本批论文已在列表中','rc-batch-change');
   heading.append(change);
   once(retrievalCues,{node:change,delay:80},'batch:'+selectedDirection+':'+batches.at(-1).id+':'+added);
  }
  const cue=selectedDirection+':'+papers.map(pid).join(',')+':'+searching;
  const active=nav.querySelector('[aria-pressed=true]');if(active)once(retrievalCues,{node:active,delay:0},'direction-cue:'+cue);if(papers.length)once(retrievalCues,{node:heading,delay:150},'result-cue:'+cue);
  col.classList.add('rc-retrieved-column');
  if(direction){const queries=el('details',null,'rc-query-detail');queries.dataset.detailKey='search:'+direction.id;queries.append(el('summary','检索词'));for(const query of new Set(currentQueries.map(s=>s.input.query)))queries.append(el('p',query));col.append(queries);}
 }
 function filtering(){
  const se=selection(),ready=Array.isArray(se.selected_papers),selected=unique(A(se.selected_papers)),excluded=unique(A(se.excluded_papers));
  const found=unique(searches().flatMap(s=>A(s.output?.papers))),assessedIds=new Set([...selected,...excluded].map(pid));
  const all=ready?unique([...found,...selected,...excluded]):found;
  const root=board();root.classList.add('rc-filter-board');root.dataset.destination=filterDestination;
  const summary=el('div',null,'rc-selection-summary');
  summary.append(el('strong',ready?`${all.length} 篇候选，${selected.length} 篇进入分析`:'正在挑选要阅读的论文'),el('span','比较问题相关性、可用摘要和研究方向覆盖'));
  const bar=el('div',null,'rc-selection-bar'),fill=el('span');fill.style.width=(all.length?selected.length/all.length*100:0)+'%';bar.append(fill);summary.append(bar);root.append(summary);once(reveals,{node:fill,delay:0,grow:true},'selection:'+selected.map(pid).join(','));
  const tabs=el('div',null,'rc-outcome-tabs');tabs.setAttribute('role','group');tabs.setAttribute('aria-label','筛选去向');
  for(const [id,label,ps] of [['selected','进入分析',selected],['excluded','未选入',excluded]]){const b=action(`${label} · ${ps.length} 篇`,()=>browse(()=>{filterDestination=id;}));b.setAttribute('aria-pressed',String(filterDestination===id));tabs.append(b);}summary.append(tabs);
  const selectedIds=new Set(selected.map(pid));
  const candidates=paperColumn(root,all,'全部候选论文','candidates',p=>!ready?'等待筛选':selectedIds.has(pid(p))?'✓ 进入分析':p.exclusion_reason||(assessedIds.has(pid(p))?'未选入':'未进入本次分析'));candidates.classList.add('rc-candidate-column');
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
 }
 function relationships(){
  const claims=[...data.claims.values()],labels=data.labels,root=board();root.classList.add('rc-relations-board');
  const papers=new Map(data.papers.map(p=>[pid(p),p.title]));
  for(const record of data.records){for(const [id,title] of Object.entries(record.input?.paper_titles||{}))papers.set(id,title);for(const p of A(record.input?.passages))if(p.paper_id)papers.set(p.paper_id,p.title||record.input?.paper||papers.get(p.paper_id));for(const c of A(record.output?.claims))if(record.input?.paper)papers.set(c.paper_id,record.input.paper);}
  const paperIds=[...new Set(claims.map(c=>c.paper_id))];
  const toolbar=el('div',null,'rc-relations-toolbar'),total=el('div',null,'rc-relations-total');
  total.append(el('strong',`${claims.length} 条原文关系`),el('span',`${paperIds.length} 篇来源论文 · 下方完整展示`));toolbar.append(total);
  const paperSelect=el('select');paperSelect.setAttribute('aria-label','按来源论文查看关系');paperSelect.append(new Option('全部来源论文','all'));paperIds.forEach((id,i)=>paperSelect.append(new Option(papers.get(id)||`来源论文 ${i+1}`,id)));paperSelect.value=relationPaper;
  const typeSelect=el('select');typeSelect.setAttribute('aria-label','按关系类型查看');const types={reported_causal:'论文报告的机制',associated_with:'相关性观察',hypothesis:'待验证假设'};
  typeSelect.append(new Option('全部关系类型','all'));for(const [id,label]of Object.entries(types))typeSelect.append(new Option(label,id));typeSelect.value=relationType;toolbar.append(paperSelect,typeSelect);root.append(toolbar);
  paperSelect.onchange=()=>{data.onBrowse?.();relationPaper=paperSelect.value;key='';update(data);stage.querySelector('[aria-label="按来源论文查看关系"]')?.focus({preventScroll:true});};
  typeSelect.onchange=()=>{data.onBrowse?.();relationType=typeSelect.value;key='';update(data);stage.querySelector('[aria-label="按关系类型查看"]')?.focus({preventScroll:true});};
  const found=claims.filter(c=>(relationPaper==='all'||c.paper_id===relationPaper)&&(relationType==='all'||c.type===relationType));
  root.append(el('p',`当前显示 ${found.length} / ${claims.length} 条 · 每张图对应一条原文关系，点击可展开依据`,'rc-relations-caption'));
  const list=el('div',null,'rc-relations-list');list.dataset.scrollKey='relations:'+relationPaper+':'+relationType;list.setAttribute('role','region');list.setAttribute('aria-label','全部原文关系');list.tabIndex=0;root.append(list);
  for(const c of found){
   const card=el('article',null,'rc-relation-card');card.dataset.claimId=c.id;card.dataset.type=c.type;
   const number=claims.indexOf(c)+1,header=el('div',null,'rc-relation-card-head');header.append(el('span',String(number).padStart(2,'0')),el('span',types[c.type]||'原文关系'));card.append(header);
   const diagram=el('div',null,'rc-relation-diagram'),source=el('div',labels[c.source]||c.source,'rc-factor'),target=el('div',labels[c.target]||c.target,'rc-factor');
   const connector=el('div',null,'rc-relation-connector');connector.append(el('span',c.type==='associated_with'?'相关':c.type==='hypothesis'?'假设影响':'影响'));
   const arrow=S('svg',{viewBox:'0 0 80 24','aria-hidden':'true'},connector),line=S('path',{d:c.type==='associated_with'?'M4 12H76':'M4 12H74m-7-6 7 6-7 6'},arrow);
   diagram.append(source,connector,target);card.append(diagram);
   const title=papers.get(c.paper_id)||'来源论文',detail=el('details',null,'rc-relation-evidence');detail.dataset.detailKey='relation:'+c.id;detail.append(el('summary','查看原句与适用条件'),el('blockquote',c.quote||'此记录未保存原句。'));
   const names={task:'任务',model:'模型',dataset:'数据集',metric:'指标',setting:'实验设置',bridge_state:'中间因素变化'};
   for(const [k,v]of Object.entries(c.conditions||{}))detail.append(el('p',`${names[k]||k}：${v==='unknown'?'未说明':v}`));card.append(el('p',title,'rc-relation-source'),detail);list.append(card);
   const identity=JSON.stringify([c.id,c.source,c.target,c.type,c.quote]);
   if(!animatedRelations.has(identity)){animatedRelations.add(identity);const delay=Math.min(reveals.length,5)*70;reveals.push({node:source,delay},{node:target,delay:delay+650});strokes.push({node:line,delay:delay+200});}
  }
  if(!found.length)list.append(el('p',claims.length?'没有符合筛选条件的关系。':data.info.status==='running'?'正在读取论文，新关系会出现在这里。':'还没有已记录的原文关系。','rc-board-empty'));
 }
 function checking(){
  const analysis=latest(s=>/路径、条件/.test(s.name||'')),paths=A(data.result?.candidate_paths||analysis.paths),checks=[...A(data.result?.rejected_links||analysis.rejected_links),...paths.flatMap(p=>A(p.checks))],root=board();root.classList.add('rc-check-board');
  const names={task:'任务',model:'模型',dataset:'数据集',metric:'指标',setting:'研究设置',bridge_state:'中间因素变化'};
  if(checks.length){
   const counts={compatible:0,conflict:0,unknown:0};checks.forEach(c=>counts[c.state in counts?c.state:'unknown']++);
   const overview=el('div',null,'rc-check-overview');
   for(const [id,label]of [['compatible','条件相符'],['conflict','存在差异'],['unknown','条件待补充']]){const metric=el('div',null,'rc-check-metric');metric.dataset.state=id;metric.append(el('strong',String(counts[id])),el('span',label));overview.append(metric);}root.append(overview);
   const list=el('div',null,'rc-check-list');list.dataset.scrollKey='checks';list.setAttribute('role','region');list.setAttribute('aria-label',`全部 ${checks.length} 项证据条件检查`);list.tabIndex=0;root.append(list);
   checks.forEach((c,i)=>{
    const left=data.claims.get(c.left),right=data.claims.get(c.right),label=c.state==='compatible'?'条件相符':c.state==='conflict'?'存在差异':'条件待补充',item=el('article',null,'rc-check-item');item.dataset.state=c.state||'unknown';
    const heading=el('div',null,'rc-check-item-heading');heading.append(el('span',`接续 ${String(i+1).padStart(2,'0')}`),el('strong',label));item.append(heading);
    const diagram=el('div',null,'rc-check-diagram');
    for(const [claim,side]of [[left,'前一段证据'],[right,'后一段证据']]){const evidence=el('div',null,'rc-check-evidence');evidence.append(el('span',side),el('blockquote',claim?.quote||'这条记录未保存对应原句。'));diagram.append(evidence);}
    item.append(diagram);const detail=el('details',null,'rc-check-details');detail.dataset.detailKey='check:'+JSON.stringify([c.left,c.right,i]);detail.append(el('summary','查看核对依据'));
    if(A(c.matches).length)detail.append(el('p','相符：'+c.matches.map(k=>names[k]||k).join('、')));
    for(const conflict of A(c.conflicts))detail.append(el('p',`${names[conflict.field]||conflict.field}：${conflict.left} / ${conflict.right}`));
    if(A(c.missing).length)detail.append(el('p','待补充：'+c.missing.map(k=>names[k]||k).join('、')));
    if(!detail.querySelector('p'))detail.append(el('p','此记录没有保存更详细的条件说明。'));item.append(detail);list.append(item);appear(item,'check:'+JSON.stringify(c),Math.min(i,6)*65);
   });summary(`完整显示 ${checks.length} 项条件检查`);return;
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
 function generation(){
  const generated=latest(s=>s.output?.answer),result=data.result?.answer?data.result:generated,answer=result.answer,sources=A(result.sources),root=board();root.classList.add('rc-generation-board');
  if(!answer){boardEmpty(root,data.info.status==='running'?'正在组织有据回答':'回答尚未生成',sources.length?`已准备 ${sources.length} 个原文片段；回答生成后将连接到这些来源。`:'已完成的论文筛选与证据整理可以在前面的阶段查看。');return;}
  const referenced=new Set([...answer.matchAll(/\[(\d+)\]/g)].map(m=>Number(m[1])).filter(i=>i<sources.length));
  const article=el('section',null,'rc-generated-answer');article.append(el('div','回答正文','rc-column-label'));
  const body=el('article',null,'rc-answer-reading markdown-body');body.dataset.scrollKey='answer';body.setAttribute('role','region');body.setAttribute('aria-label','完整回答正文');body.tabIndex=0;
  const inspectSource=i=>{const source=sources[i];if(!source)return;for(const card of root.querySelectorAll('[data-source-index]'))card.classList.toggle('rc-source-current',Number(card.dataset.sourceIndex)===i);inspect(source.title||'论文来源',[source.text||source.abstract||'此记录未保存原文。'],`引用 [${i}]`);};
  if(window.researchReader){const sections=researchReader.sections(result);researchReader.render(body,sections.body,{sources,onCitation:inspectSource});}else body.append(el('p',answer));
  article.append(body);root.append(article);appear(article,'answer-ready');
  const evidence=el('section',null,'rc-answer-sources');evidence.append(el('div',`来源 · ${unique(sources).length} 篇论文`,'rc-column-label'));
  const list=el('div',null,'rc-complete-papers');list.dataset.scrollKey='answer-sources';list.setAttribute('role','region');list.setAttribute('aria-label','全部回答来源');list.tabIndex=0;
  sources.forEach((p,i)=>{const item=card(p,i,referenced.has(i)?'正文已引用':'输入的原文片段',`answer-source:${i}:${pid(p)}`);item.dataset.sourceIndex=i;item.querySelector('.rc-document-number').textContent=`[${i}]`;item.setAttribute('aria-label',`引用 [${i}]：${p.title||'论文来源'}`);item.onclick=()=>inspectSource(i);list.append(item);});
  if(!sources.length)list.append(el('p','这份记录未保存来源。','rc-board-empty'));evidence.append(list);root.append(evidence);summary(`完整回答正文与 ${sources.length} 个来源片段，点击引用核对原文`);
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
  if(changedRun){animatedRelations.clear();seenVisuals.clear();scrollPositions.clear();openDetails.clear();relationPaper='all';relationType='all';seenItems.clear();selectedDirection='all';filterDestination='selected';sceneRun=next.run.id;scenePhase=-1;}
  if(next.phase===1&&next.following&&(next.run.status==='running'||next.searchId)){
   const requests=searches().filter(s=>!s.output?.retry_scheduled&&!/连接重试/.test(s.name||''));
   const current=requests.find(s=>s.id===next.searchId)||requests.reduce((last,s)=>(s.seq||0)>(last?.seq||-1)?s:last,null);
   if(current){const direction=dimensions().find(d=>current.input?.dimension===d.id||current.input?.query===d.query||current.input?.query===d.followup_query);selectedDirection=direction?.id||'all';}
  }
  const contentKeys=[()=>[next.run.question,dimensions()],()=>[searches().map(s=>[s.id,s.status,s.input,s.output?.papers]),dimensions(),selectedDirection],()=>[searches().map(s=>s.output?.papers),selection(),filterDestination],()=>[[...next.claims.values()],next.labels,next.papers.map(p=>[pid(p),p.title]),relationPaper,relationType],()=>[latest(s=>/路径、条件/.test(s.name||'')),next.result?.candidate_paths,next.result?.rejected_links,scope(),[...next.claims.values()]],()=>[next.result?.answer?next.result:latest(s=>s.output?.answer)]];
  const nextKey=JSON.stringify([next.run.id,next.phase,next.info.status,contentKeys[next.phase]()]);if(nextKey===key)return settled;
  if(!changedRun){for(const n of stage.querySelectorAll('[data-scroll-key]'))scrollPositions.set(n.dataset.scrollKey,n.scrollTop);
   for(const detail of stage.querySelectorAll('[data-detail-key]')){if(detail.open)openDetails.add(detail.dataset.detailKey);else openDetails.delete(detail.dataset.detailKey);}}
  const active=document.activeElement,focus=stage.contains(active)?{paper:active.dataset.paperId,direction:active.dataset.direction,scroll:active.dataset.scrollKey,source:active.dataset.sourceIndex}:null;
  scenePhase=next.phase;key=nextKey;
  cancel();strokes=[];reveals=[];htmlMoves=[];retrievalCues=[];if(changedRun||changedPhase)q('.rc-inspector').hidden=true;stage.replaceChildren();stage.removeAttribute('aria-description');stage.classList.remove('rc-stage-board');q('.rc-title').textContent=titles[next.phase];
  q('.rc-heading .rc-eyebrow').textContent=`第 ${next.phase+1} 步 / 共 ${titles.length} 步`;
  const state=q('.rc-scene-state');state.dataset.state=next.info.status;state.textContent=({running:'正在更新',done:'已记录',error:'暂时中断',stopped:'已停止',waiting:'等待结果'})[next.info.status]||'已记录';
  [planning,retrieval,filtering,relationships,checking,generation][next.phase]();
  for(const detail of stage.querySelectorAll('[data-detail-key]'))detail.open=openDetails.has(detail.dataset.detailKey);
  for(const list of stage.querySelectorAll('[data-scroll-key]'))list.scrollTop=scrollPositions.get(list.dataset.scrollKey)||0;
  if(focus&&!changedPhase&&!changedRun){const target=[...stage.querySelectorAll('button,[data-scroll-key]')].find(n=>focus.source!==undefined?n.dataset.sourceIndex===focus.source:focus.paper?n.dataset.paperId===focus.paper:focus.direction?n.dataset.direction===focus.direction:focus.scroll&&n.dataset.scrollKey===focus.scroll);target?.focus({preventScroll:true});}
  alignRetrievalLink();return animate();
 }
 function closeInspector(){q('.rc-inspector').hidden=true;if(inspectorTrigger?.isConnected)inspectorTrigger.focus({preventScroll:true});}
 q('.rc-close').onclick=closeInspector;
 host.addEventListener('keydown',e=>{if(e.key==='Escape'&&!q('.rc-inspector').hidden){closeInspector();e.stopPropagation();}});
 const linkLayoutObserver=new ResizeObserver(()=>{alignRetrievalLink();});linkLayoutObserver.observe(stage);
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
 function sourcesAndClaims(){const claims=new Map(),labels={...(state.result?.entity_labels||{})};for(const s of records()){Object.assign(labels,s.input?.entity_labels||{});for(const c of [...arr(s.output?.claims),...arr(s.input?.candidate_claims)])claims.set(c.id,c);for(const e of arr(s.output?.entities))labels[e.id]=e.name;}return {claims,labels};}
 function renderScope(){const r=state.result||{},selected=latestOut(s=>s.output?.selected_papers),request=records().find(s=>/摘要筛选与/.test(s.name||''))?.input||{},sources=arr(r.sources),box=$s('story-scope');box.replaceChildren();$s('story-scope-panel').hidden=!sources.length&&!selected.selected_papers;if($s('story-scope-panel').hidden)return;const indexed=r.corpus_stats?.indexed??selected.selected_papers?.length??'—',candidates=r.corpus_stats?.candidates??request.candidates??'—',used=r.sources?uniquePapers(sources):'—';$s('story-scope-summary').textContent=`证据范围：${indexed} 篇进入分析 · ${used} 篇用于回答 · 查看覆盖详情`;box.append(E('strong','这次研究实际用了多少证据'),note(`${candidates} 篇候选 → ${indexed} 篇进入分析 → ${used} 篇用于回答`));if(r.sources){const paths=arr(r.paths);box.append(note(`${sources.length} 个原文片段；${paths.filter(single).length} 条单关系记录；${paths.filter(cross).length} 条跨论文链。`,'fine'));}const scope=r.evidence_scope||latestOut(s=>s.output?.unique_papers!==undefined&&s.output?.dimensions);if(scope.dimensions){const list=E('div',null,'coverage-grid');for(const d of scope.dimensions){const card=E('div');card.append(E('strong',d.label),E('span',`${d.paper_ids.length} 篇含定位原句的来源`),E('small',!d.paper_ids.length?'当前回答缺少该维度依据':d.paper_ids.length===1?'单篇来源':'多篇来源'));list.append(card);}box.append(list);}else if(r.sources)box.append(note('这份记录未保存维度覆盖分析。','fine'));}
 function phaseSummaries(rs,claims){
  const result=state.result||{},plan=result.research_plan||latestOut(s=>s.output?.plan).plan;
  const searches=rs.filter(s=>s.kind==='http'&&s.input?.query);
  const recordedPapers=searches.flatMap(s=>arr(s.output?.papers));
  const returned=searches.some(s=>Array.isArray(s.output?.papers));
  const count=rs.find(s=>/摘要筛选与/.test(s.name||''))?.input?.candidates??latestOut(s=>s.output?.unique_candidates!==undefined).unique_candidates??(returned?uniquePapers(recordedPapers):undefined);
  const selectedPapers=latestOut(s=>s.output?.selected_papers).selected_papers;
  const read=rs.filter(s=>/论文实体与关系/.test(s.name||'')&&s.status==='success').length;
  const analysis=latestOut(s=>/路径、条件/.test(s.name||'')),paths=arr(result.candidate_paths||analysis.paths);
  const checks=paths.reduce((sum,path)=>sum+arr(path.checks).length,0)+arr(result.rejected_links||analysis.rejected_links).length;
  const sources=result.sources||latestOut(s=>s.output?.answer).sources;
  const recorded=[Boolean(plan),returned,Array.isArray(selectedPapers),claims.size>0,checks>0||Boolean(result.evidence_scope?.dimensions?.length),Boolean(result.answer)];
  const metrics=[plan?`${arr(plan.dimensions).length} 个研究方向`:'等待研究方向', count!==undefined?`${count} 篇候选论文`:'等待检索结果',
   selectedPapers?`${selectedPapers.length} 篇进入分析`:'等待筛选结果',claims.size?`${claims.size} 条原文关系`:read?`${read} 篇已阅读`:'等待原文关系',
   checks?`${checks} 项条件核对`:'核对结果已记录',sources?`${uniquePapers(arr(sources))} 篇回答来源`:'等待回答生成'];
  return metrics.map((metric,i)=>{
   const events=rs.filter(s=>phase(s)===i||(i===3&&/路径、条件/.test(s.name||'')));
   let status='waiting';
   if(events.some(s=>s.status==='error'))status='error';
   else if(state.run.status==='running'&&events.some(s=>!s.status||s.status==='running'))status='running';
   else if(events.some(s=>s.status==='success')||recorded[i])status='done';
   else if(events.length)status='stopped';
   if(status==='waiting')metric='尚无记录';
   else if(i===4&&!checks&&status!=='done')metric='等待核对结果';
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
 function enqueue(frame){if(queue.at(-1)?.displayPhase===frame.displayPhase&&queue.at(-1)?.displaySearchId===frame.displaySearchId)queue[queue.length-1]=frame;else queue.push(frame);}
 function receive(s){
  if(!s.run?.id)return;
  const signature=JSON.stringify([s.run.id,s.run.status,s.result,[...(s.steps?.values()||[])].map(x=>[x.id,x.seq,x.status,x.output])]);
  if(signature===incomingKey){drain();return;}incomingKey=signature;
  const previous=incoming,copy=structuredClone(s);incoming=copy;
  if(lastId!==s.run.id){clearQueue();lastId=s.run.id;following=true;selected=null;lastKey='';wasLive=false;state=copy;}
  const live=wasLive||s.run.status==='running';wasLive=live;
  if(!live||!following){state=copy;if(!host.hidden)render();return;}
  const sameRun=previous?.run?.id===s.run.id,old=sameRun?previous.steps:new Map(),working=new Map(old||[]);
  const changed=[...(copy.steps?.values()||[])].filter(x=>{const before=old?.get(x.id);return !before||before.seq!==x.seq||before.status!==x.status||JSON.stringify(before.output)!==JSON.stringify(x.output);}).sort((a,b)=>(a.seq||0)-(b.seq||0));
  for(const step of changed){working.set(step.id,step);if(step.kind==='llm'||/跨文献检索与生成$|结构化输出/.test(step.name||''))continue;
   const n=phase(step);
   const search=n===1?[...working.values()].filter(s=>s.kind==='http'&&s.input?.query&&!s.output?.retry_scheduled&&!/连接重试/.test(s.name||'')).reduce((last,s)=>(s.seq||0)>(last?.seq||-1)?s:last,null):null;
   enqueue({...copy,steps:new Map(working),result:n===5?copy.result:null,displayPhase:n,displaySearchId:search?.id});
  }
  if(copy.result?.answer&&copy.run.status==='success')enqueue({...copy,displayPhase:5});
  else if(previous?.run?.status!==copy.run.status)enqueue({...copy,displayPhase:queue.at(-1)?.displayPhase??selected??0,displaySearchId:queue.at(-1)?.displaySearchId??state.displaySearchId});
  if(!queue.length&&!draining){state=copy;if(!host.hidden)render();}else drain();
 }
 const queueVisibility=new MutationObserver(()=>{if(visibleJourney())drain();});
 queueVisibility.observe(document.body,{attributes:true,subtree:true,attributeFilter:['hidden','data-screen']});
 document.addEventListener('visibilitychange',()=>{if(!document.hidden)drain();});
 return {update:receive,render:()=>{if(!draining&&!queue.length)render();drain();},reset:()=>{clearQueue();lastKey='';incomingKey='';}};
};
