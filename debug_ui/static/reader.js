/* Marked is used only for tokenization. Untrusted HTML is never inserted into the DOM. */
window.researchReader = (() => {
 const element=(tag,text)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;return e;};
 function render(target,markdown,{sources=[],onCitation=()=>{}}={}){
  const text=(parent,value,links=true)=>{
   for(const part of String(value||'').split(/(\[\d+\])/g)){
    const match=links&&/^\[(\d+)\]$/.exec(part),index=match?Number(match[1]):-1;
    if(index>=0&&sources[index]){const b=element('button',part);b.className='citation';b.type='button';b.title=sources[index].title;b.setAttribute('aria-label',`查看证据 ${index}：${sources[index].title}`);b.onclick=()=>onCitation(index,b.closest('p,li,td,blockquote')?.textContent||'',b);parent.append(b);}else parent.append(document.createTextNode(part));
   }
  };
  function inline(parent,tokens=[]){for(const t of tokens){
   if(['strong','em','del','codespan'].includes(t.type)){const e=element({strong:'strong',em:'em',del:'del',codespan:'code'}[t.type]);if(t.type==='codespan')text(e,t.text,false);else inline(e,t.tokens||[]);parent.append(e);}
   else if(t.type==='link'){let safe=false;try{safe=['https:','http:'].includes(new URL(t.href).protocol);}catch{}if(safe){const a=element('a');a.href=t.href;a.target='_blank';a.rel='noopener noreferrer';inline(a,t.tokens);parent.append(a);}else inline(parent,t.tokens);}
   else if(t.type==='br')parent.append(element('br'));
   else if(t.type==='image')text(parent,t.text||'[图片未加载]',false);
   else if(t.tokens)inline(parent,t.tokens);
   else text(parent,t.text??t.raw,t.type!=='html');
  }}
  function blocks(parent,tokens){for(const t of tokens){
   if(t.type==='space')continue;
   if(t.type==='heading'){const h=element('h'+Math.min(4,Math.max(2,t.depth)));inline(h,t.tokens);parent.append(h);}
   else if(t.type==='paragraph'||t.type==='text'){const p=element('p');t.tokens?inline(p,t.tokens):text(p,t.text);parent.append(p);}
   else if(t.type==='list'){const list=element(t.ordered?'ol':'ul');if(t.ordered&&t.start!==1)list.start=t.start;for(const item of t.items){const li=element('li');if(item.task)li.append(element('span',item.checked?'☑ ':'☐ '));blocks(li,item.tokens);list.append(li);}parent.append(list);}
   else if(t.type==='table'){const wrap=element('div');wrap.className='table-scroll';wrap.tabIndex=0;wrap.setAttribute('role','region');wrap.setAttribute('aria-label','可横向滚动的比较表格');const table=element('table'),head=element('thead'),tr=element('tr');for(const cell of t.header){const th=element('th');th.scope='col';inline(th,cell.tokens);tr.append(th);}head.append(tr);table.append(head);const body=element('tbody');for(const row of t.rows){const r=element('tr');for(const cell of row){const td=element('td');inline(td,cell.tokens);r.append(td);}body.append(r);}table.append(body);wrap.append(table);parent.append(wrap);}
   else if(t.type==='blockquote'){const q=element('blockquote');blocks(q,t.tokens);parent.append(q);}
   else if(t.type==='code'){const p=element('pre');p.append(element('code',t.text));parent.append(p);}
   else if(t.type==='hr')parent.append(element('hr'));
   else if(t.type==='html')parent.append(element('p',t.text||t.raw));
   else if(t.tokens)blocks(parent,t.tokens);else if(t.raw)parent.append(element('p',t.raw));
  }}
  target.replaceChildren();try{blocks(target,marked.lexer(String(markdown||''),{gfm:true}));}catch{target.append(element('p',markdown));}
 }
 function sections(result={}){
  const answer=String(result.answer||'');
  if(Object.prototype.hasOwnProperty.call(result,'evidence_review'))return {body:answer,evidence:String(result.evidence_review||'')};
  // Older records remain unchanged on disk. Move whole Markdown sections, including children.
  const body=[],evidence=[];let evidenceDepth=0;
  try{for(const token of marked.lexer(answer,{gfm:true})){
   if(token.type==='heading'){
    if(evidenceDepth&&token.depth<=evidenceDepth)evidenceDepth=0;
    const heading=token.text.replace(/^[一二三四五六七八九十\d]+[、.．：:）)]\s*/, '');
    if(/^(?:证据范围|证据与|证据梳理|按.*证据梳理|研究方法与局限|局限(?:性)?与|未回答的|所需证据|Evidence (?:scope|review|limitations)|Limitations)/i.test(heading))evidenceDepth=token.depth;
   }
   const raw=token.type==='heading'?(token.raw||'').replace(/^(#{1,6}\s+)[一二三四五六七八九十]+[、.．：:]\s*/, '$1'):(token.raw||'');
   (evidenceDepth?evidence:body).push(raw);
  }}catch{return {body:answer,evidence:''};}
  return {body:body.join('').trim(),evidence:evidence.join('').trim()};
 }
 return {render,sections};
})();
