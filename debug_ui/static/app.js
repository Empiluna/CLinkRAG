const $=id=>document.getElementById(id);
const statusNames={running:'研究中',success:'已完成',error:'执行失败',cancelled:'已停止',interrupted:'已中断'};
const methodNames={clinkrag_online:'CLinkRAG · 在线检索',clinkrag:'CLinkRAG · 本地资料库',scirag_fixed:'SciRAG · 固定资料库',scirag:'SciRAG · 在线检索'};
let token='',run=null,result=null,steps=new Map(),order=[],cursor=0,selected=null,polling=false,liveId=null;
let historyKey='',dimensionQuestion='';
let connected=false,config={},submitting=false,connecting=false,pollTicket=0,submissionId=null,toastTimer=null;
const format=value=>typeof value==='string'?value:JSON.stringify(value,null,2);
const duration=s=>s==null?'—':s<60?`${s.toFixed(1)} 秒`:`${Math.floor(s/60)} 分 ${Math.floor(s%60)} 秒`;
const node=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
function notice(message){$('notice').hidden=!message;$('notice').textContent=message||'';}
function toast(message){$('toast').textContent=message;$('toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').hidden=true,3000);}
function storageRead(key){try{return localStorage.getItem(key);}catch{return null;}}
function storageWrite(key,value){try{localStorage.setItem(key,value);return true;}catch{return false;}}
function setConnection(state){connected=state==='online';$('connection-state').dataset.state=state;$('connection').textContent={online:'本地服务已连接',offline:'连接已断开',checking:'正在连接…'}[state];$('reconnect').hidden=state!=='offline';updateControls();}
function updateControls(){const missing=!config.llm_configured||(['scirag','clinkrag_online'].includes($('method').value)&&!config.s2_configured);const disabled=!connected||submitting||!!liveId||missing;const label=submitting?'正在提交…':liveId?'已有研究运行中':!connected?'等待连接':missing?'请先配置 API':'开始研究';$('submit').disabled=disabled;$('submit').textContent=label;if($('home-start')){$('home-start').disabled=disabled||!$('home-question').value.trim();$('home-start').title=label;}$('cancel').disabled=!connected||run?.status!=='running';}
async function api(path,options={}){
 const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),12000);
 try{const response=await fetch(path,{...options,signal:controller.signal,headers:{'Content-Type':'application/json','X-SciRAG-Token':token,...options.headers}});const data=await response.json();if(!response.ok){const error=new Error(data.error||`服务返回 ${response.status}`);error.status=response.status;error.code=data.code;if(response.status===403)setConnection('offline');throw error;}return data;}
 catch(error){if(!error.status){setConnection('offline');throw new Error(error.name==='AbortError'?'本地服务响应超时，请重新连接。':'无法连接本地服务。请确认 start-ui.ps1 正在运行。');}throw error;}
 finally{clearTimeout(timer);}
}
function switchTab(answer){window.researchApp?.hideJourney();window.paperGraph?.hide();document.body.dataset.view=answer?'answer':'trace';$('compare-view').hidden=true;$('compare-tab').classList.remove('active');$('compare-tab').setAttribute('aria-selected','false');$('trace-view').hidden=answer;$('answer-view').hidden=!answer;for(const [id,on] of [['trace-tab',!answer],['answer-tab',answer]]){$(id).classList.toggle('active',on);$(id).setAttribute('aria-selected',on);}}
function pick(id){selected=id;renderSteps();renderDetail();}
function readableRunError(error){
 const raw=String(error||'本次研究没有完成。');
 if(!raw.includes('api.semanticscholar.org'))return raw;
 if(/CERTIFICATE_VERIFY_FAILED|certificate verify failed|hostname mismatch/i.test(raw))return '无法验证论文检索服务的安全证书。请检查代理或系统证书配置，原始错误保留在技术记录中。';
 if(/SSLError|SSLEOFError|UNEXPECTED_EOF|ConnectionError|Max retries exceeded|timed?\s*out/i.test(raw))return '连接论文检索服务时意外断开或超时，未能完成这组论文检索。请检查网络或代理后继续研究。';
 return raw;
}
function renderEmptyAnswer(){
 const state=run?.status,failed=['error','cancelled','interrupted'].includes(state),running=state==='running';
 document.body.dataset.runState=state||'loading';
 document.body.dataset.hasAnswer=String(!!result?.answer);
 const network=state==='error'&&/api\.semanticscholar\.org|Semantic Scholar.*(?:连接|超时)/i.test(run?.error||'');
 $('empty-kicker').textContent=running?'正在研究':failed?'研究未完成':'等待回答';
 $('empty-title').textContent=network?'论文检索中断':state==='cancelled'?'研究已停止':state==='interrupted'?'研究已中断':state==='error'?'这次研究未能完成':running?'回答正在形成':'正在读取研究记录';
 $('empty-description').textContent=network?'与 Semantic Scholar 的连接中断，本次尚未形成回答。':state==='error'?'处理过程中遇到了问题，已经完成的步骤仍然保留。':failed?'本次没有生成完整回答，已完成的步骤仍然保留。':'系统正在整理问题和证据，完成后会在这里展示回答与引用。';
 $('empty-guidance').textContent=network?'点击继续研究，从已保存的检索进度接着运行。':'先回看研究过程，了解已经找到的材料和当前进展。';
 $('empty-retry').hidden=!failed;$('empty-cost').hidden=true;$('empty-retry').textContent=run?.method==='clinkrag_online'?'继续研究':'重新研究';
 $('empty-error-details').hidden=!run?.error;$('empty-error-text').textContent=run?.error||'';
 $('empty-duration').textContent=$('elapsed').textContent;
 const completed=[...steps.values()].filter(s=>s.status==='success'&&s.kind!=='llm'&&s.kind!=='http');
 $('empty-completed').textContent=String(completed.length);
 const last=completed.filter(s=>!/结构化输出|本次研究参数|运行模型配置/.test(s.name)).at(-1)||completed.at(-1);
 $('empty-last-step').textContent=last?.name==='在线检索 · 查询规划'?'研究维度与检索词规划':last?.name||'暂无已完成步骤';
 $('empty-graph').textContent=running?'查看实时研究过程':'查看已保存的过程';
}
function renderRun(){
 if(!run)return;$('welcome').hidden=true;$('research-content').hidden=false;
 $('run-title').textContent=run.question||'正在载入研究…';$('run-method').textContent=methodNames[run.method||'scirag'];$('run-meta').textContent=run.created_at?`${new Date(run.created_at).toLocaleString('zh-CN')} · ${duration(run.elapsed??result?.elapsed)} · ${['scirag','clinkrag_online'].includes(run.method||result?.method||'scirag')?'在线检索资料':'固定 28 篇论文摘要与片段'}`:'';
 $('run-status').textContent=statusNames[run.status]||'载入中';$('run-status').className='badge '+(run.status||'');$('download').disabled=false;
 const done=order.filter(id=>steps.get(id).status==='success').length;$('steps-count').textContent=`${done} / ${order.length}`;$('llm-count').textContent=order.filter(id=>steps.get(id).kind==='llm').length;$('source-count').textContent=result?.sources?new Set(result.sources.map(s=>s.id)).size:'—';
 $('elapsed').textContent=duration(run.status==='running'?(Date.now()-Date.parse(run.resumed_at||run.created_at))/1000:run.elapsed??result?.elapsed);
 $('progress-strip').hidden=run.status!=='running';const current=[...steps.values()].reverse().find(s=>!s.status&&s.kind!=='llm'&&s.kind!=='http');$('progress-title').textContent=current?.name||'正在等待研究进程';$('progress-description').textContent=`已完成 ${done} 个步骤 · 已运行 ${$('elapsed').textContent}。总步骤随检索分支变化；页面刷新不会重复提交。`;
 const failed=['error','cancelled','interrupted'].includes(run.status);$('run-recovery').hidden=!failed;
 if(failed){const resumable=run.method==='clinkrag_online';$('recovery-title').textContent=statusNames[run.status];$('recovery-description').textContent=readableRunError(run.error)+(resumable?' 点击继续研究，将复用已保存的查询、论文与摘要核对结果。':' 已完成的步骤保留。');$('retry-run').textContent=resumable?'继续研究':'重新研究';$('retry-run').title=resumable?'从保存的进度继续当前研究':'使用原问题新建研究';}
 const retry=[...steps.values()].reverse().find(s=>s.name==='在线检索 · 连接重试'),retryParent=retry&&steps.get(retry.parent);
 if(run.status==='running'&&retryParent&&!retryParent.status){
  const delay=Math.max(0,Math.ceil((Date.parse(retry.time)+Number(retry.input.delay_seconds)*1000-Date.now())/1000));
  $('progress-title').textContent='论文检索连接暂时中断，正在恢复';
  $('progress-description').textContent=delay?`${retry.input.reason}，${delay} 秒后进行第 ${retry.input.next_attempt}${retry.input.max_attempts?'/'+retry.input.max_attempts:''} 次请求。`:`正在进行第 ${retry.input.next_attempt}${retry.input.max_attempts?'/'+retry.input.max_attempts:''} 次请求；可随时停止，稍后继续。`;
 }
 renderEmptyAnswer();updateControls();window.researchApp?.update({run,result,steps});
}
let answerReadingRun=null;
function showAnswerReading(mode){
 const evidence=mode==='evidence';
 $('answer-main-panel').hidden=evidence;$('answer-evidence-panel').hidden=!evidence;
 $('read-body').setAttribute('aria-pressed',String(!evidence));$('read-evidence').setAttribute('aria-pressed',String(evidence));
}
function renderAnswer(){
 const ready=!!result?.answer;document.body.dataset.hasAnswer=String(ready);$('answer-empty').hidden=ready;$('answer-content').hidden=!ready;if(!ready){$('answer-text').replaceChildren();return;}
 const sources=result.sources||[],papers=new Set(sources.map(s=>s.id)).size;$('evidence-summary').textContent=`${papers} 篇来源 · ${sources.length} 条原始证据`;
 $('evidence-caveat').textContent=(result.warnings||[]).map(researchNotice).filter(Boolean).join(' ');
 if(result.generation_warning)$('evidence-caveat').textContent+=' '+result.generation_warning;
 $('evidence-caveat').hidden=!$('evidence-caveat').textContent.trim();
 const reading=researchReader.sections(result);
 researchReader.render($('answer-text'),reading.body,{sources,onCitation:openEvidence});
 researchReader.render($('evidence-review-text'),reading.evidence,{sources,onCitation:openEvidence});
 $('evidence-review-text').hidden=!reading.evidence;
 $('answer-completion-note').textContent=result.generation_warning||'';$('answer-completion-note').hidden=!result.generation_warning;
 if(answerReadingRun!==run?.id){answerReadingRun=run?.id;showAnswerReading('body');}
 renderPaths();$('path-section').hidden=!result.paths?.length;$('path-count').textContent=result.paths?`${result.paths.filter(p=>new Set(p.paper_ids).size>1).length} 条跨论文链`:'无';
 $('sources-label').textContent=`${papers} 篇 / ${sources.length} 条证据`;$('sources').replaceChildren();
 sources.forEach((s,i)=>{const b=node('button',undefined,'source');b.id='source-'+i;b.append(node('span',String(i).padStart(2,'0'),'source-index'),node('span',s.title||'未命名论文','source-name'),node('span','↗','source-arrow'));b.onclick=()=>openEvidence(i,'',b);$('sources').append(b);});
}
function researchNotice(value){
 const text=String(value||'');
 // Omit this known boilerplate from older saved runs; retain concrete run issues.
 if(text==='仅使用返回摘要；未读取全文。维度归属与研究类型为模型判断，不是质量认证。')return '';
 if(['部分摘要末尾疑似不完整；不补写缺失部分，请核对论文原文。','部分摘要末尾可能不完整。','摘要末尾可能不完整（标点启发式，需人工核对）'].includes(text.trim()))return '';
 if(/^找到与问题直接相关的论文\s*\d+\s*篇，分析上限为\s*\d+\s*篇。?$/.test(text.trim()))return '';
 return text;
}
function openEvidence(index,context='',trigger=null,focusQuote=null){
 const source=result?.sources?.[index];if(!source)return;const body=$('evidence-body');body.replaceChildren();const title=node('h2',source.title||'未命名论文');title.id='evidence-title';body.append(node('span',`证据 [${index}]`,'badge'),title);
 if(/^[a-f0-9]{40}$/i.test(source.id||'')){const a=node('a','在 Semantic Scholar 打开论文 ↗');a.href='https://www.semanticscholar.org/paper/'+source.id;a.target='_blank';a.rel='noopener noreferrer';body.append(a);}
 if(context){body.append(node('h3','答案中引用此证据的段落'),node('p',context,'citation-context'));}
 body.append(node('h3','本次使用的原始文本'));const original=node('div',undefined,'original-text');
 const relations=(result.paths||[]).flatMap(p=>p.relations||[]).filter(r=>r.passage_id===source.passage_id);
 const quote=focusQuote&&source.text?.includes(focusQuote)?focusQuote:null;const at=quote?source.text.indexOf(quote):-1;
 if(at>=0){original.append(document.createTextNode(source.text.slice(0,at)),node('mark',quote),document.createTextNode(source.text.slice(at+quote.length)));}else original.textContent=source.text||'本次记录没有提供文本。';body.append(original);
 if(relations.length){body.append(node('h3','该片段已提取的关系条件'));body.append(node('p','以下条件属于系统提取的关系，不一定对应当前引用段落。','fine'));for(const r of relations){const detail=node('details');detail.append(node('summary','查看关系原句与条件'),node('p',r.quote||'','original-text'),node('pre',JSON.stringify(r.conditions||{},null,2),'payload'));body.append(detail);}}

 const dialog=$('evidence-drawer');if(!dialog.open)dialog.showModal();dialog.scrollTop=0;$('close-evidence').focus();
}
function closeEvidence(){if($('evidence-drawer').open)$('evidence-drawer').close();}
async function history(){
 const items=await api('/api/runs');liveId=items.find(item=>item.status==='running')?.id||null;updateControls();
 const nextKey=JSON.stringify([run?.id,items]);if(nextKey===historyKey)return items;historyKey=nextKey;
 const list=$('history'),scrollTop=list.scrollTop,focusedId=list.contains(document.activeElement)?document.activeElement.dataset.runId:null;
 list.replaceChildren();if(!items.length)list.append(node('p','还没有历史研究','fine'));
 for(const item of items){
  const row=node('div',undefined,'history-entry'+(item.id===run?.id?' selected':''));row.dataset.status=item.status||'';
  const b=node('button');b.type='button';b.dataset.runId=item.id;b.className='history-open';
  if(item.id===run?.id)b.setAttribute('aria-current','page');
  b.title=`${item.question}\n${statusNames[item.status]||item.status} · ${new Date(item.created_at).toLocaleString('zh-CN')}`;
  b.append(node('strong',item.question));if(item.status==='error'){b.setAttribute('aria-label',item.question+'，执行失败');const mark=node('span','失败','history-failed-label');b.append(mark);}
  b.onclick=()=>{document.body.classList.remove('sidebar-open');$('mobile-menu').setAttribute('aria-expanded','false');loadRun(item.id).catch(e=>notice(e.message));};
  const remove=node('button','×','history-remove');remove.type='button';remove.title='删除研究';remove.setAttribute('aria-label','删除研究：'+item.question);remove.onclick=()=>askDeleteResearch(item);
  row.append(b,remove);list.append(row);
 }
 list.scrollTop=scrollTop;
 if(focusedId)[...list.querySelectorAll('[data-run-id]')].find(b=>b.dataset.runId===focusedId)?.focus({preventScroll:true});
 window.researchApp?.history(items);return items;
}

let resuming=false;
async function requireRunCapability(name){
 const current=await api('/api/config');config=current;token=current.token;
 if(!current.capabilities?.[name])throw new Error('本地服务仍是旧版本，请关闭原启动窗口，再运行 start-ui.ps1。已有研究进度会保留。');
}
async function continueResearch(){
 if(run?.method!=='clinkrag_online'){openComposer(true);return;}
 if(resuming||!connected)return;
 const id=run.id;resuming=true;$('retry-run').disabled=true;$('empty-retry').disabled=true;
 try{await requireRunCapability('resume');const resumed=await api(`/api/runs/${id}/resume`,{method:'POST'});liveId=resumed.id;await loadRun(id);$('journey-tab').click();}
 catch(e){notice(e.message);}
 finally{resuming=false;$('retry-run').disabled=false;$('empty-retry').disabled=false;updateControls();}
}
function clearCurrentResearch(){
 pollTicket++;polling=false;closeEvidence();window.paperGraph?.reset();window.paperGraph?.hide();
 run=null;result=null;steps=new Map();order=[];cursor=0;selected=null;answerReadingRun=null;
 try{localStorage.removeItem('scirag-run');}catch{}
 $('research-content').hidden=true;$('download').disabled=true;renderAnswer();
 window.researchApp?.update({run,result,steps});window.researchApp?.open('home');updateControls();
}
let deleteTarget=null,deleteBusy=false;
function askDeleteResearch(item){
 deleteTarget=item;$('delete-question').textContent=item.question||'未命名研究';
 $('delete-time').textContent=new Date(item.created_at).toLocaleString('zh-CN');
 $('delete-description').textContent=item.status==='running'?'这项研究将先停止，再永久删除正文、研究过程与记录。删除后无法恢复。':'将永久删除这项研究的正文、研究过程与记录。删除后无法恢复。';
 $('delete-confirm').textContent=item.status==='running'?'停止并永久删除':'永久删除';$('delete-error').hidden=true;
 $('delete-research-dialog').showModal();$('delete-cancel').focus();
}
async function deleteResearch(){
 if(!deleteTarget||deleteBusy)return;const item=deleteTarget;deleteBusy=true;$('delete-confirm').disabled=true;$('delete-cancel').disabled=true;
 try{await requireRunCapability('permanent_delete');await api(`/api/runs/${item.id}/delete`,{method:'POST',body:JSON.stringify({confirm_permanent:true})});
  if(liveId===item.id)liveId=null;if(run?.id===item.id)clearCurrentResearch();
  $('delete-research-dialog').close();historyKey='';await history();toast('研究已永久删除。');
 }catch(e){$('delete-error').textContent=e.message;$('delete-error').hidden=false;}
 finally{deleteBusy=false;$('delete-confirm').disabled=false;$('delete-cancel').disabled=false;}
}
async function loadRun(id,{navigate=true}={}){
 closeEvidence();window.paperGraph?.reset();run={id};if(navigate)window.researchApp?.open('research',true);cursor=0;steps=new Map();order=[];selected=null;result=null;renderAnswer();notice('');$('steps').replaceChildren();$('detail').replaceChildren();$('detail-status').textContent='未选择';switchTab(true);renderRun();storageWrite('scirag-run',id);window.scrollTo({top:0});await poll(true);await history();
}
async function poll(force=false){
 if(!run?.id||(polling&&!force))return;polling=true;const identity=run.id,ticket=++pollTicket;
 try{const data=await api(`/api/runs/${identity}?after=${cursor}`);if(run?.id!==identity||ticket!==pollTicket)return;const wasRunning=run.status==='running',oldAnswer=result?.answer;run=data.run;result=data.result;
 for(const event of data.events){cursor=Math.max(cursor,event.seq);if(event.event==='start'){if(!steps.has(event.id))order.push(event.id);steps.set(event.id,{...event,status:null});}else if(steps.has(event.id))Object.assign(steps.get(event.id),event,{time:steps.get(event.id).time});}
 if(run.status!=='running'){for(const step of steps.values())if(!step.status)step.status=run.status==='success'?'error':run.status;if(liveId===run.id)liveId=null;}
 if(!selected&&order.length)selected=order[0];renderRun();if(data.events.length||(wasRunning&&run.status!=='running')){renderSteps();renderDetail();}if(oldAnswer!==result?.answer)renderAnswer();if(data.events.length)window.paperGraph?.refresh();if(wasRunning&&run.status!=='running')await history();
 }catch(e){if(run?.id===identity&&e.code==='run_not_found'){clearCurrentResearch();history().catch(()=>{});toast(e.message);}else notice(e.message+' 已加载的结果仍可阅读。');}finally{if(ticket===pollTicket)polling=false;}
}
function formData(){return {...runOptions.values(),question:$('question').value,method:'clinkrag_online',initial_papers:Number($('initial-papers').value),max_tokens:Number($('max-tokens').value),...($('method').value==='clinkrag_online'?{online_papers:Number($('online-papers').value),research_dimensions:$('research-dimensions').value.split(/\n/).map(s=>s.trim()).filter(Boolean)}:{})};}
function saveDraft(changed=false){const question=$('question').value.trim();if(dimensionQuestion&&question!==dimensionQuestion&&$('research-dimensions').value.trim()){$('research-dimensions').value='';if(changed&&question)toast('问题已修改，检索方向将重新规划。');}dimensionQuestion=$('research-dimensions').value.trim()?question:'';if(changed)submissionId=null;const ok=storageWrite('clinkrag-draft',JSON.stringify({...formData(),dimensions_question:dimensionQuestion,client_request_id:submissionId}));$('draft-status').textContent=ok?'草稿已保存在本机':'浏览器未允许保存，请先复制问题';}
function methodHint(){runOptions.refresh();const mode=$('method').value;$('online-options').hidden=mode!=='clinkrag_online';$('method-hint').textContent=mode==='clinkrag_online'?'根据你的问题在线检索，使用可获取的论文摘要。分析篇数越多，耗时和费用越高。':mode==='scirag'?'在线查询 Semantic Scholar，适合其他研究主题。资料范围与固定语料实验不同。':mode==='clinkrag'?'使用已构建的 28 篇 RAG 主题论文摘要与片段。其他领域的问题可能缺少足够证据。':'使用同一 28 篇 RAG 资料库运行原版 SciRAG 流程，固定使用 3 篇种子。';updateControls();}
function showComposerPanel(key){
 const dialog=$('research-dialog');
 for(const panel of dialog.querySelectorAll('[data-composer-panel]'))panel.hidden=panel.dataset.composerPanel!==key;
 for(const button of dialog.querySelectorAll('[data-composer-section]'))button.setAttribute('aria-pressed',String(button.dataset.composerSection===key));
 dialog.querySelector('.composer-panels').scrollTop=0;
}
function setResearchSelect(id,value){const select=$(id),text=String(value);if(![...select.options].some(o=>o.value===text))select.add(new Option(text,text));select.value=text;}
function openComposer(copyRun=false,preserveDraft=false){
 if(!copyRun&&!preserveDraft)window.researchApp?.applyDefaults();
 if(copyRun&&run?.question){runOptions.restore(run);$('question').value=run.question;$('method').value=run.method||'scirag';setResearchSelect('initial-papers',run.initial_papers||3);setResearchSelect('online-papers',run.online_papers||12);$('research-dimensions').value=(run.research_dimensions||[]).join('\n');dimensionQuestion=run.question.trim();setResearchSelect('max-tokens',run.max_tokens||1800);saveDraft(true);}
 $('method').value='clinkrag_online';if(!preserveDraft){methodHint();window.researchApp?.open('home');$('home-question')?.focus();return;}showComposerPanel('retrieval');$('composer-error').hidden=true;methodHint();document.body.classList.remove('sidebar-open');$('mobile-menu').setAttribute('aria-expanded','false');if(!$('research-dialog').open)$('research-dialog').showModal();$('research-dialog').querySelector('[data-composer-section="retrieval"]').focus();
}
async function connect(){
 if(connecting)return;connecting=true;if(!connected)setConnection('checking');
 try{config=await api('/api/config');token=config.token;$('model').textContent=config.model||'未设置';$('device').textContent=config.device||'未设置';$('s2').textContent=config.s2_configured?'已配置':'未配置';setConnection('online');const items=await history();notice('');
 if(run?.id)await poll(true);else{const saved=storageRead('scirag-run'),id=liveId||(items.some(x=>x.id===saved)?saved:items[0]?.id);if(id)await loadRun(id,{navigate:false});else{$('welcome').hidden=false;$('research-content').hidden=true;}}
 if(!config.llm_configured)notice('请在 config.local.yaml 配置模型 API；历史结果和图谱仍可查看。');
 }catch(e){setConnection('offline');notice(e.message);if(!run)$('welcome').hidden=false;}
 finally{connecting=false;}
}
function downloadText(text,filename){const url=URL.createObjectURL(new Blob([text],{type:'text/markdown;charset=utf-8'})),a=node('a');a.href=url;a.download=filename;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function setup(){
 try{const draft=JSON.parse(storageRead('clinkrag-draft')||'null');if(draft){runOptions.restore(draft);for(const [id,key,min,max]of [['initial-papers','initial_papers',1,8],['max-tokens','max_tokens',500,12000]])if(Number.isInteger(draft[key])&&draft[key]>=min&&draft[key]<=max)setResearchSelect(id,draft[key]);if(Number.isInteger(draft.online_papers)&&draft.online_papers>=3&&draft.online_papers<=30)setResearchSelect('online-papers',draft.online_papers);$('question').value=String(draft.question||'');dimensionQuestion=String(draft.dimensions_question??draft.question??'').trim();$('research-dimensions').value=dimensionQuestion===$('question').value.trim()&&dimensionQuestion?(draft.research_dimensions||[]).join('\n'):'';for(const [id,key] of [['method','method'],['initial-papers','initial_papers'],['online-papers','online_papers'],['max-tokens','max_tokens']])if([...$(id).options].some(o=>o.value===String(draft[key])))$(id).value=String(draft[key]);submissionId=draft.client_request_id||null;}}catch{}
 methodHint();
 $('run-form').addEventListener('input',()=>{saveDraft(true);runOptions.refresh();});$('run-form').addEventListener('change',()=>{saveDraft(true);methodHint();});
 $('run-form').onsubmit=async event=>{event.preventDefault();if($('research-dialog').open){$('research-dialog').close();return;}if(window.modelSettings?.isBusy()){toast('模型正在保存，请稍候');return;}if(submitting)return;if(!config.llm_configured||!config.s2_configured){toast('请先在设置中配置模型和检索 API');return;}if(!connected){toast('请先连接本地服务');return;}if(liveId){toast('已有研究运行中，请等待完成');return;}const payload=formData();if(payload.question.trim().length<5||payload.question.trim().length>4000){toast('请输入 5–4,000 字的研究问题');return;}submissionId=submissionId||crypto.randomUUID();saveDraft();const signature=JSON.stringify(payload);submitting=true;updateControls();$('composer-error').hidden=true;
 try{const item=await api('/api/runs',{method:'POST',body:JSON.stringify({...payload,client_request_id:submissionId})});liveId=item.id;if(JSON.stringify(formData())===signature){$('question').value='';submissionId=null;saveDraft();}$('research-dialog').close();await loadRun(item.id);}
 catch(e){$('composer-error').textContent=e.message+' 若提交结果不明确，请先重连并检查历史；相同提交编号的重试会复用已有任务。';$('composer-error').hidden=false;toast(e.message);}
 finally{submitting=false;updateControls();}};
 $('new-research').onclick=$('welcome-start').onclick=$('scope-info').onclick=()=>openComposer();$('rerun').onclick=()=>openComposer(true);$('retry-run').onclick=continueResearch;
 for(const button of $('research-dialog').querySelectorAll('[data-composer-section]'))button.onclick=()=>showComposerPanel(button.dataset.composerSection);
 $('run-form').addEventListener('invalid',e=>{const panel=e.target.closest('[data-composer-panel]');if(panel)showComposerPanel(panel.dataset.composerPanel);},true);
 $('composer-done').onclick=()=>$('research-dialog').close();
 $('close-composer').onclick=()=>$('research-dialog').close();$('research-dialog').addEventListener('close',()=>saveDraft());$('close-evidence').onclick=closeEvidence;
 for(const id of ['research-dialog','evidence-drawer'])$(id).addEventListener('click',e=>{const r=$(id).getBoundingClientRect();if(e.target===$(id)&&(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom))$(id).close();});
 $('technical').onchange=renderSteps;$('trace-tab').onclick=()=>switchTab(false);$('answer-tab').onclick=()=>switchTab(true);$('empty-graph').onclick=()=>$('journey-tab').click();$('empty-retry').onclick=continueResearch;$('empty-trace').onclick=()=>switchTab(false);
 $('reconnect').onclick=connect;
 $('delete-confirm').onclick=deleteResearch;$('delete-cancel').onclick=()=>$('delete-research-dialog').close();
 $('delete-research-dialog').addEventListener('cancel',e=>{if(deleteBusy)e.preventDefault();});
 $('cancel').onclick=async()=>{if(!run||!connected)return;$('cancel').disabled=true;try{await api(`/api/runs/${run.id}/cancel`,{method:'POST'});await poll(true);await history();}catch(e){notice(e.message);}finally{updateControls();}};
 $('download').onclick=()=>{if(run)window.location.href=`/api/runs/${run.id}/export`;};
 $('read-body').onclick=()=>showAnswerReading('body');$('read-evidence').onclick=()=>showAnswerReading('evidence');
 $('copy-answer').onclick=async()=>{try{await navigator.clipboard.writeText(researchReader.sections(result||{}).body);toast('正文已复制');}catch{toast('浏览器未允许复制，请使用导出 Markdown');}};
 $('export-answer').onclick=()=>{if(result){const reading=researchReader.sections(result);downloadText(`# ${run.question}\n\n## 正文\n\n${reading.body}\n\n## 证据与梳理\n\n${reading.evidence}\n\n## 本次原始证据\n\n`+(result.sources||[]).map((s,i)=>`### [${i}] ${s.title}\n\n${s.text}`).join('\n\n'),'CLinkRAG-研究记录.md');}};
 const closeNav=()=>{document.body.classList.remove('sidebar-open');$('mobile-menu').setAttribute('aria-expanded','false');$('mobile-menu').focus();};
 $('mobile-menu').onclick=()=>{const opened=document.body.classList.toggle('sidebar-open');$('mobile-menu').setAttribute('aria-expanded',String(opened));};
 $('sidebar-backdrop').onclick=closeNav;
 document.addEventListener('keydown',e=>{if(e.key==='Escape'){document.body.classList.remove('sidebar-open');$('mobile-menu').setAttribute('aria-expanded','false');}});
 document.querySelector('[role=tablist]').addEventListener('keydown',e=>{const tabs=[...document.querySelectorAll('[role=tab]')],i=tabs.indexOf(document.activeElement);if(i<0)return;let next;if(e.key==='ArrowRight')next=(i+1)%tabs.length;if(e.key==='ArrowLeft')next=(i+tabs.length-1)%tabs.length;if(e.key==='Home')next=0;if(e.key==='End')next=tabs.length-1;if(next!==undefined){e.preventDefault();tabs[next].focus();tabs[next].click();}});
 setInterval(()=>{if(connected&&run?.status==='running'){poll();renderRun();}},1500);
 setInterval(()=>{if(!document.hidden&&!submitting)connect();},12000);connect();
}

function labeledOutput(step){
 const output=step.output;if(!Array.isArray(output))return output;
 if(step.name==='知识缺口检查 / 生成子问题')return {'是否停止追加检索':output[0],'追加检索子问题':output[1],'原代码估算费用（非账单）':output[2]};
 if(['回答提纲','初始回答','生成子问题回答','反思与修改','逐段引用归因'].includes(step.name))return {'生成内容':output[0],'原代码估算费用（非账单）':output[1]};
 if(['候选资料检索、扩展与筛选','自底向上汇总答案与来源'].includes(step.name))return {'回答':output[0],'参考资料':output[1],'原代码估算费用（非账单）':output[2]};
 if(step.name==='Semantic Scholar 片段检索与引文扩展')return {'检索资料':output[0],'是否执行引文扩展':output[1],'原代码估算费用（非账单）':output[2]};
 if(step.name==='三步论文关系推理与筛选')return {'保留论文与选择理由':output[0],'原代码估算费用（非账单）':output[1]};
 if(step.name==='02 · SciRAG 主流程')return {'最终回答':output[0],'原代码估算费用（非账单）':output[1],'来源':output[2]};
 return output;
}
function depth(step){let level=0,p=step.parent;while(p&&steps.has(p)&&level<8){level++;p=steps.get(p).parent;}return level;}
function renderSteps(){
 const container=$('steps');if(!order.length)return;const oldScroll=container.scrollTop;container.replaceChildren();
 for(const id of order){const step=steps.get(id);if(!$('technical').checked&&['llm','http'].includes(step.kind))continue;
 const httpWarning=step.output?.http_status>=400;
 const button=document.createElement('button');button.type='button';button.className=`step ${step.status||'running'} ${id===selected?'selected':''} ${httpWarning?'warning':''}`;button.style.marginLeft=`${Math.min(depth(step),3)*6}px`;button.style.width=`calc(100% - ${Math.min(depth(step),3)*6}px)`;
 const symbol=document.createElement('span');symbol.className='step-symbol';symbol.textContent=httpWarning?'!':step.status==='success'?'✓':step.status==='error'?'!':step.status==='cancelled'?'—':'·';
 const main=document.createElement('span');main.className='step-main';const title=document.createElement('span');title.className='step-title';title.textContent=step.name;main.append(title);
 const sub=document.createElement('span');sub.className='step-sub';sub.textContent=(typeof step.input?.query==='string'?step.input.query:null)||step.input?.father?.node?.query||(step.kind!=='http'?step.input?.path:null)||({llm:'查看完整提示词与模型响应',http:`HTTP ${step.output?.http_status||'等待响应'} · ${step.input?.method||''}`,gpu:'查看候选评分与实际设备'})[step.kind]||`STEP ${order.indexOf(id)+1} · ${statusNames[step.status]||'运行中'}`;main.append(sub);
 const time=document.createElement('span');time.className='step-time';time.textContent=duration(step.elapsed);button.append(symbol,main,time);button.onclick=()=>pick(id);container.append(button);
 }container.scrollTop=oldScroll;
}
function renderDetail(){const step=steps.get(selected);if(!step)return;const container=$('detail');container.replaceChildren();$('detail-status').textContent=statusNames[step.status]||'运行中';const title=document.createElement('h4');title.textContent=step.name;const meta=document.createElement('div');meta.className='detail-meta';meta.textContent=`${new Date(step.time).toLocaleTimeString()} · ${duration(step.elapsed)} · ${step.kind} · ${step.id}`;container.append(title,meta);
 const tips={'加载 BGE 重排模型':'模型初始化时可能暂在 CPU；请以随后评分步骤的 device 字段核对实际计算设备。','知识缺口检查 / 生成子问题':'输出依次为：是否终止、追加子问题、旧算法费用字段（不作为实际账单）。终止时后续扩展和归因不会执行。','三步论文关系推理与筛选':'展开下属模型调用，依次查看内容分类、关系提取和最终选文。','自底向上汇总答案与来源':'输出依次为：汇总回答、合并后的来源、旧算法费用字段。','01 · 自动初始检索':'自动生成英文检索词，获取论文摘要。无可用摘要时显示检索状态。','候选资料检索、扩展与筛选':'输出依次为：子问题回答、筛选后的论文（含 score / rationale）、旧算法费用字段。'};
 const out=step.output;if(out&&typeof out==='object'&&!Array.isArray(out)){const phase=Array.isArray(out.candidates)?'retrieved':Array.isArray(out.ranked)?'pool':Array.isArray(out.sources)?'context':Array.isArray(out.paths)?'retrieved':null;if(phase){const jump=document.createElement('button');jump.className='graph-step-jump';jump.textContent='↗ 在论文关系图中查看这一阶段';jump.onclick=()=>window.paperGraph?.showPhase(phase);container.append(jump);}}
 if(tips[step.name]){const p=document.createElement('p');p.className='detail-tip';p.textContent=tips[step.name];container.append(p);}
 for(const [label,value,error] of [['输出 / 返回结果',labeledOutput(step),false],['输入 / 参数 / 提示词',step.input,false],['错误与调用栈',step.error?`${step.error}\n\n${step.traceback||''}`:undefined,true]]){if(value===undefined)continue;const details=document.createElement('details');details.className='detail-section';details.open=label!=='输入 / 参数 / 提示词'||!step.status;const summary=document.createElement('summary');summary.textContent=label;details.append(summary);const fields=value&&typeof value==='object'&&!Array.isArray(value)?Object.entries(value):[['',value]];for(const [key,content] of fields){if(key){const heading=document.createElement('h5');heading.textContent=key;details.append(heading);}const pre=document.createElement('pre');pre.className='payload'+(error?' error':'');pre.textContent=format(content);details.append(pre);}container.append(details);}
 if(!step.status){const p=document.createElement('p');p.className='fine';p.textContent='正在执行。完成后会显示输出；等待 API 返回时页面继续更新其他状态。';container.append(p);}
}

function renderPaths(){
 let container=$('path-results');if(!container){container=document.createElement('section');container.id='path-results';$('path-section').append(container);}container.replaceChildren();
 if(!result?.paths)return;
 const heading=document.createElement('h3');heading.textContent=`原文关系记录 ${result.paths.filter(p=>p.relations?.length===1).length} 条 · 跨论文链 ${result.paths.filter(p=>new Set(p.paper_ids).size>1).length} 条`;container.append(heading);
 if(result.fallback_reason){const tip=document.createElement('p');tip.className='fine';tip.textContent='本次没有采用跨论文解释链；回答使用直接检索到的证据。';container.append(tip);}
 for(const path of result.paths){const card=document.createElement('details');card.className='source';const summary=document.createElement('summary');const names=result.entity_labels||{};summary.textContent=path.relations.map(r=>`${names[r.source]||r.source} → ${names[r.target]||r.target}`).join(' / ')+` · ${path.state==='uncertain'?'条件未充分对齐':'原文关系'} · ${path.paper_ids.length} 篇`;card.append(summary);
 for(const relation of path.relations){const quote=document.createElement('p');quote.textContent=relation.quote;card.append(quote);const condition=document.createElement('p');condition.className='fine';condition.textContent='适用条件：'+JSON.stringify(relation.conditions);card.append(condition);const i=result.sources.findIndex(s=>s.passage_id===relation.passage_id);if(i>=0){const button=document.createElement('button');button.className='text-button';button.textContent=`查看来源 [${i}]`;button.onclick=()=>{openEvidence(i,'',button,relation.quote);};card.append(button);}}
 container.append(card);
 }
}


$('compare-tab').onclick=async()=>{window.researchApp?.hideJourney();window.paperGraph?.hide();
 switchTab(false);$('trace-view').hidden=true;$('answer-view').hidden=true;$('compare-view').hidden=false;
 for(const id of ['trace-tab','answer-tab']){$(id).classList.remove('active');$(id).setAttribute('aria-selected','false');}
 document.body.dataset.view='compare';$('compare-tab').classList.add('active');$('compare-tab').setAttribute('aria-selected','true');
 const target=$('comparison-results');try{const data=await api('/api/comparison');target.replaceChildren();
 const labels={vanilla:'普通 RAG',scirag_roles:'SciRAG 原版贡献重排（组件）',clinkrag_no_assoc:'CLinkRAG 去掉共现',clinkrag_no_paths:'CLinkRAG 去掉路径',clinkrag:'CLinkRAG'};
 const table=document.createElement('table');table.className='comparison-table';const head=document.createElement('tr');for(const text of ['问题','方法','必要论文覆盖','自动论断支持','秒']){const th=document.createElement('th');th.textContent=text;head.append(th);}table.append(head);
 for(const r of data.rows){const tr=document.createElement('tr');for(const text of [r.question_id,labels[r.method]||r.method,Math.round(100*r.required_paper_coverage)+'%',r.automated_review?.supported_claim_fraction==null?'—':Math.round(100*r.automated_review.supported_claim_fraction)+'%',r.online_seconds]){const td=document.createElement('td');td.textContent=text;tr.append(td);}table.append(tr);}target.append(table);
 const note=document.createElement('p');note.className='fine';note.textContent='SciRAG 组件组只测试原版三步贡献关系重排，并非整个系统。完整 SciRAG 固定语料结果在下面单列，它包含额外模型调用，上下文预算不同。共现统计与建图成本也不包含在在线秒数中。';target.append(note);
 for(const result of data.full_scirag){if(!result?.answer)continue;const detail=document.createElement('details');detail.className='source';const summary=document.createElement('summary');summary.textContent='完整 SciRAG：'+result.question;const text=document.createElement('article');text.className='markdown-body';researchReader.render(text,result.answer);detail.append(summary,text);target.append(detail);}
 if(data.rows.length){const conclusion=document.createElement('p');conclusion.className='detail-tip';conclusion.textContent='本批共 3 道开发问题，均未选入跨论文路径；移除共现边后，候选集与最终上下文保持一致。';target.prepend(conclusion);}else target.textContent='对照测试尚未完成。';
 }catch(e){target.textContent=e.message;}
};

setup();
