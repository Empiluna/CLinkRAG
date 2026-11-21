/* Local reading desk. Uploaded material stays in memory until the tab is closed. */
(() => {
  const desk = $('literature-screen');
  desk.innerHTML = `
    <header class="desk-heading"><h1>文献查证</h1><p>输入问题，在论文中定位相关段落，核对出处。</p></header>
    <form id="lit-form"><fieldset id="lit-controls">
      <label for="lit-question">查证问题</label>
      <textarea id="lit-question" rows="2" minlength="2" maxlength="1500" required placeholder="想从文献中核对什么？"></textarea>
      <fieldset class="collection-choice"><legend>资料来源</legend>
        <label><input type="radio" name="collection" value="builtin" checked><span>示例文献</span></label>
        <label><input type="radio" name="collection" value="personal"><span>我的资料</span></label>
        <label><input type="radio" name="collection" value="crossref"><span>在线查找</span></label>
      </fieldset>
      <p class="desk-note" id="lit-scope"></p>
      <div id="lit-language" hidden><label for="lit-english">补充英文检索词（可选）</label>
        <input id="lit-english" maxlength="240" placeholder="例如 urban heat island">
        <button type="button" id="lit-translate" class="text-button" hidden>生成英文检索词</button><small id="lit-translate-note" hidden>点击会将问题发送给当前模型。</small>
      </div>
      <div id="lit-personal" hidden>
        <div class="material-actions"><label class="file-action">导入 PDF 或 TXT<input type="file" id="lit-files" multiple accept=".pdf,.txt,application/pdf,text/plain"></label>
          <button type="button" id="lit-paste-toggle" aria-expanded="false" aria-controls="lit-paste">粘贴文本</button></div>
        <details id="lit-pdf-range"><summary>PDF 读取页码</summary><p class="desk-note">可选。每次最多读取 100 页、5 万字。请导入可复制文字的 PDF。</p>
          <div><label>从第 <input id="lit-first-page" type="number" min="1" step="1" placeholder="1"> 页</label><label>到第 <input id="lit-last-page" type="number" min="1" step="1" placeholder="末页"> 页</label></div></details>
        <div id="lit-paste" hidden><label for="lit-title">资料标题</label><input id="lit-title" maxlength="300">
          <label for="lit-text">原文</label><textarea id="lit-text" rows="4" maxlength="50000" placeholder="粘贴摘要或正文，用于本次查证"></textarea>
          <button type="button" id="lit-add">添加到本次资料</button></div>
        <ul id="lit-papers" aria-label="已加入的资料"></ul>
      </div>
      <footer class="desk-submit"><label for="lit-limit">最多显示 <select id="lit-limit">${[1,2,3,4,5,6,7,8,9,10].map(n=>`<option ${n===5?'selected':''}>${n}</option>`).join('')}</select> 条</label>
        <button type="submit" class="primary" id="lit-search">查找原文</button></footer>
    </fieldset></form>
    <p class="desk-status" id="lit-status" role="status" aria-live="polite"></p>
    <section id="lit-results" hidden aria-labelledby="lit-result-title"><header class="findings-heading"><div><h2 id="lit-result-title" tabindex="-1">查证结果</h2><p id="lit-result-query"></p></div>
      <div class="desk-exports"><button type="button" id="lit-md">导出笔记</button><button type="button" id="lit-ris">导出文献 RIS</button></div></header>
      <p id="lit-note" class="desk-note"></p><ol id="lit-items" class="evidence-ledger"></ol>
      <section id="lit-brief-section" hidden><h3>整理研究发现</h3><p id="lit-brief-notice"></p>
        <button id="lit-brief" type="button" class="secondary">用模型整理所选原文</button>
        <button type="button" id="lit-connect" class="text-button" hidden>设置回答模型</button>
        <p id="brief-status" role="status"></p><div id="brief-content"></div></section></section>`;

  const materials = [];
  let catalog, finding, busy = false, briefBusy = false, resultVersion = 0, importing = false;
  let responseSelection = new Set(), translating = false;
  const collection = () => desk.querySelector('input[name="collection"]:checked').value;
  const itemKey = (_, index) => String(index);
  const status = (message, failed = false) => {
    $('lit-status').textContent = message;
    $('lit-status').classList.toggle('failed', failed);
  };

  function scope() {
    $('lit-personal').hidden = collection() !== 'personal';
    $('lit-language').hidden = collection() === 'builtin';
    $('lit-translate').hidden = $('lit-translate-note').hidden = !connected || !config.llm_configured;
    $('lit-scope').textContent = {
      builtin: catalog ? `随附 ${catalog.count} 篇文献，可在本机直接查证。` : '使用随项目附带的文献，在本机查证。',
      personal: '可加入 1–20 篇文本。单篇最多 5 万字，共 30 万字。',
      crossref: '查找时会将问题发送至 Crossref，使用其公开文献记录。'
    }[collection()];
  }

  async function getCatalog() {
    if (!catalog) catalog = await api('/api/literature');
    scope();
    return catalog;
  }

  function clearBrief() {
    $('brief-status').textContent = '';
    $('brief-content').replaceChildren();
  }

  function resetFindings() {
    resultVersion++;
    finding = null;
    briefBusy = false;
    responseSelection.clear();
    $('lit-results').hidden = true;
    clearBrief();
  }

  function editSource(paper, rowName) {
    const editor=node('details');
    editor.className='source-editor';
    editor.append(node('summary','修改出处'));
    const title=node('input');title.value=paper.title;title.maxLength=500;
    const url=node('input');url.type='url';url.value=paper.url||'';url.placeholder='https://…';
    const save=node('button','保存出处');save.type='button';
    const error=node('p');error.setAttribute('role','status');
    for(const [caption,field] of [['资料标题',title],['出处链接（可选）',url]]){
      const label=node('label',caption);label.append(field);editor.append(label);
    }
    save.onclick=()=>{
      const name=title.value.trim(),address=url.value.trim();
      if(!name){error.textContent='请填写标题。';title.focus();return;}
      if(address&&!sourceLink(address)){error.textContent='请输入有效的 http 或 https 链接。';url.focus();return;}
      paper.title=name;paper.url=address;rowName.textContent=name;
      resetFindings();drawMaterials();status('已保存出处。');
    };
    editor.append(save,error);
    return editor;
  }

  function drawMaterials() {
    $('lit-papers').replaceChildren(...materials.map((paper, index) => {
      const row = node('li');
      const name = node('span', paper.title);
      const remove = node('button', '移除');
      remove.type = 'button';
      remove.setAttribute('aria-label', '移除 '+paper.title);
      remove.onclick = () => {materials.splice(index,1);drawMaterials();resetFindings();};
      row.append(name, node('small', paper.text.length.toLocaleString()+' 字'), remove, editSource(paper,name));
      return row;
    }));
  }

  function addMaterials(additions) {
    const combined = materials.concat(additions);
    if (combined.length > 20) throw new Error('最多可加入 20 篇，请先移除一篇资料。');
    if (additions.some(p => !p.text.trim() || p.text.length > 50000)) throw new Error('每篇资料需有正文，最多 5 万字。');
    if (combined.reduce((n,p) => n+p.text.length,0) > 300000) throw new Error('资料总长度超过 30 万字，请分批查证。');
    materials.push(...additions);
    resetFindings();
    drawMaterials();
    status(`已加入 ${additions.length} 篇资料，共 ${materials.length} 篇。`);
  }

  $('lit-paste-toggle').onclick = () => {
    const panel = $('lit-paste');
    panel.hidden = !panel.hidden;
    $('lit-paste-toggle').setAttribute('aria-expanded',String(!panel.hidden));
    if (!panel.hidden) $('lit-title').focus();
  };
  $('lit-add').onclick = () => {
    const text = $('lit-text').value.trim();
    try {
      addMaterials([{title: $('lit-title').value.trim() || '文本资料 '+(materials.length+1), text}]);
      $('lit-title').value = $('lit-text').value = '';
      $('lit-paste-toggle').click();
    } catch (e) {status(e.message,true);}
  };
  $('lit-files').onchange = async event => {
    const files = [...event.target.files];
    if (!files.length || importing) return;
    importing = true;
    $('lit-controls').disabled = true;
    try {
      if (files.length + materials.length > 20) throw new Error('一次最多处理 20 篇资料。');
      const additions=[];
      for (const file of files) {
        if (/\.pdf$/i.test(file.name)) {
          if (file.size>10*1024*1024) throw new Error('单份 PDF 不能超过 10 MiB。');
          const first=$('lit-first-page').value, last=$('lit-last-page').value;
          if(first&&(!Number.isInteger(Number(first))||Number(first)<1)||
             last&&(!Number.isInteger(Number(last))||Number(last)<1)||
             last&&(Number(last)<Number(first||1)||Number(last)-Number(first||1)>=100))
            throw new Error('PDF 页码须为正整数，起止范围最多 100 页。');
          const range=new URLSearchParams();
          if(first)range.set('first',first);
          if(last)range.set('last',last);
          status('正在本机读取 '+file.name+'…');
          const parsed=await api('/api/literature/pdf'+(range.size?'?'+range:''),{
            method:'POST',headers:{'Content-Type':'application/pdf'},body:file
          },60000);
          additions.push({title:parsed.title||file.name.replace(/\.pdf$/i,''),text:parsed.text,pages:parsed.pages});
          continue;
        }
        if (!/\.txt$/i.test(file.name) || file.size>200000) throw new Error('请选择可复制文字的 PDF 或 UTF-8 编码的 TXT 文件。');
        const text = await file.text();
        if (text.includes('\u0000') || text.includes('\uFFFD')) throw new Error(file.name+' 的文本编码无法读取。请另存为 UTF-8 TXT 后再导入。');
        additions.push({title:file.name.replace(/\.txt$/i,''),text});
      }
      addMaterials(additions);
    } catch (e) {status(e.message,true);}
    finally {importing=false;$('lit-controls').disabled=busy;event.target.value='';}
  };

  function download(text, filename, type) {
    const url=URL.createObjectURL(new Blob([text],{type}));
    const link=node('a');link.href=url;link.download=filename;
    document.body.append(link);link.click();link.remove();
    setTimeout(()=>URL.revokeObjectURL(url),1500);
  }
  function sourceLink(value) {
    try {
      const address=new URL(value);
      if (!['https:','http:'].includes(address.protocol)||address.username||address.password) return null;
      const link=node('a','打开论文');link.href=address.href;link.target='_blank';link.rel='noopener noreferrer';return link;
    } catch {return null;}
  }
  function controls() {
    const enabled=connected&&!!config.llm_configured;
    $('lit-brief').disabled=briefBusy||!enabled||!responseSelection.size;
    $('lit-connect').hidden=enabled;
    $('lit-brief-notice').textContent=enabled
      ? `将问题和勾选的 ${responseSelection.size} 条原文发送给当前模型（${config.model||'已配置模型'}）。`
      : '连接回答模型后，可将勾选的原文整理为带出处的发现。';
  }
  function showFindings(data) {
    finding=data;
    $('lit-results').hidden=false;
    $('lit-note').textContent=data.note||'';
    $('lit-result-title').textContent=`找到 ${data.items.length} 条相关原文`;
    $('lit-result-query').textContent=data.question;
    $('lit-items').replaceChildren();
    responseSelection=new Set(data.items.map(itemKey));
    data.items.forEach((item,index)=>{
      const row=node('li');row.id='lit-source-'+index;
      const header=node('header'),label=node('label'),choose=document.createElement('input');
      choose.type='checkbox';choose.checked=true;choose.setAttribute('aria-label','选择 '+item.title);
      choose.onchange=()=>{if(choose.checked)responseSelection.add(itemKey(item,index));else responseSelection.delete(itemKey(item,index));clearBrief();controls();};
      label.append(choose,node('span','来源 '+(index+1)));
      header.append(label);
      if(item.year)header.append(node('span',String(item.year)));
      if(item.page_start)header.append(node('span',item.page_end&&item.page_start!==item.page_end?`第 ${item.page_start}–${item.page_end} 页`:`第 ${item.page_start} 页`));
      const link=sourceLink(item.url);if(link)header.append(link);
      row.append(header,node('h3',item.title||'未命名资料'));
      const authors=Array.isArray(item.authors)?item.authors:[], attribution=node('p',authors.slice(0,3).join('、')+(authors.length>3?' 等':''),'paper-attribution');
      if(item.license){const license=sourceLink(item.license);if(license){license.textContent='原文许可';attribution.append(' ',license);}}
      if(attribution.textContent.trim())row.append(attribution);
      row.append(node('blockquote',item.quote));
      if(Number.isInteger(item.start)&&Number.isInteger(item.end)){
        const position=node('details',undefined,'source-location');
        position.append(node('summary','核对引用位置'));
        position.append(node('p',`收录原文第 ${item.start+1} 至 ${item.end} 个字符。`));
        if(item.match_basis==='title_or_keywords')position.append(node('p','通过标题或主题词找到本文。请阅读原文判断它能否回答问题。'));
        if(data.collection==='personal'){
          const id=/^local-(\d+)$/.exec(item.paper_id);
          const paper=id&&materials[Number(id[1])-1];
          if(paper){
            const chars=[...paper.text],excerpt=node('p',undefined,'source-context');
            if(chars.slice(item.start,item.end).join('')===item.quote){
              excerpt.append(chars.slice(Math.max(0,item.start-210),item.start).join(''),node('mark',item.quote),chars.slice(item.end,item.end+210).join(''));
              position.append(excerpt);
            }
          }
        }
        row.append(position);
      }
      $('lit-items').append(row);
    });
    $('lit-brief-section').hidden=!data.items.length;
    $('lit-md').disabled=!data.markdown;
    $('lit-ris').disabled=!data.ris;
    controls();
  }
  $('lit-md').onclick=()=>finding&&download(finding.markdown,'文献查证.md','text/markdown;charset=utf-8');
  $('lit-ris').onclick=()=>finding&&download(finding.ris,'文献查证.ris','application/x-research-info-systems');
  $('lit-connect').onclick=()=>window.researchApp.open('settings');
  $('lit-brief').onclick=async()=>{
    if(!finding||briefBusy||!config.llm_configured||!responseSelection.size)return;
    const version=resultVersion;
    const selected=finding.items.filter((item,index)=>responseSelection.has(itemKey(item,index)));
    briefBusy=true;controls();clearBrief();
    desk.querySelectorAll('#lit-items input').forEach(e=>e.disabled=true);
    $('brief-status').textContent='模型正在根据所选原文整理…';
    try {
      const data=await api('/api/literature/brief',{method:'POST',body:JSON.stringify({question:finding.question,items:selected})},115000);
      if(version!==resultVersion)return;
      const list=node('ul');list.className='brief-findings';
      data.findings.forEach(f=>{
        const item=node('li');
        const index=finding.items.findIndex(s=>s.paper_id===f.paper_id&&s.quote.includes(f.quote));
        item.append(node('p',f.claim),node('blockquote',f.quote));
        if(index>=0){
          const jump=node('button','回看来源 '+(index+1),'text-button');jump.type='button';
          jump.onclick=()=>$('lit-source-'+index).querySelector('input').focus();item.append(jump);
        }
        list.append(item);
      });
      $('brief-content').append(list);
      if(data.limitations)$('brief-content').append(node('h4','证据局限'),node('p',data.limitations));
      if(data.markdown){
        const save=node('button','导出研究发现','secondary');save.type='button';save.onclick=()=>download(data.markdown,'研究发现.md','text/markdown;charset=utf-8');$('brief-content').append(save);
      }
      $('brief-status').textContent=`${data.model||'当前模型'} 已整理 ${data.findings.length} 项发现。`;
    }catch(e){if(version===resultVersion)$('brief-status').textContent=e.message;}
    finally{if(version===resultVersion){briefBusy=false;controls();desk.querySelectorAll('#lit-items input').forEach(e=>e.disabled=false);}}
  };
  async function search() {
    if(busy||translating||importing||!$('lit-form').reportValidity())return;
    const question=$('lit-question').value.trim();
    if(question.length<2||question.length>1500){status('问题长度须为 2–1500 个字符。',true);return;}
    const source=collection();
    if(source==='personal'&&(!materials.length||(!$('lit-paste').hidden&&$('lit-text').value.trim()))){
      status(materials.length?'请先点击「添加到本次资料」保存粘贴的文本。':'请先导入 PDF、TXT 或添加粘贴的原文。',true);return;
    }
    busy=true;resetFindings();$('lit-controls').disabled=true;$('lit-search').textContent='查找中…';
    status(source==='crossref'?'正在从 Crossref 查找公开文献…':'正在匹配问题与原文…');
    try{
      const data=await api('/api/literature/search',{method:'POST',body:JSON.stringify({question,collection:source,...(source!=='builtin'&&$('lit-english').value.trim()?{english_query:$('lit-english').value.trim()}:{}),limit:Number($('lit-limit').value),...(source==='personal'?{papers:materials}:{})})},35000);
      showFindings(data);status(data.items.length?'':'试试更具体的专业术语，或换一批资料。');
      if(document.body.dataset.screen==='literature')$('lit-result-title').focus();
    }catch(e){status(e.message,true);}
    finally{busy=false;$('lit-controls').disabled=false;$('lit-search').textContent='查找原文';}
  }
  desk.querySelectorAll('input[name="collection"]').forEach(el=>el.onchange=()=>{scope();resetFindings();status('');});
  $('lit-translate').onclick=async()=>{
    if(translating||busy||!connected||!config.llm_configured)return;
    const question=$('lit-question').value.trim();
    if(question.length<2||question.length>1500){status('请先填写 2–1500 字的问题。',true);$('lit-question').focus();return;}
    translating=true;
    $('lit-controls').disabled=true;
    status('正在为当前问题生成英文检索词…');
    try {
      const data=await api('/api/literature/terms',{method:'POST',body:JSON.stringify({question})},115000);
      $('lit-english').value=data.english_query||'';
      status('可编辑英文检索词后再查找。');
    } catch(e){status(e.message,true);}
    finally{translating=false;$('lit-controls').disabled=false;$('lit-english').focus();}
  };
  $('lit-form').onsubmit=e=>{e.preventDefault();search();};
  $('open-literature').onclick=()=>{
    const question=$('home-question').value.trim();
    if(question&&!busy){$('lit-question').value=question;resetFindings();if(question.length>1500)status('这道问题超过 1500 字，请缩短后查证。',true);}
    window.researchApp.open('literature');$('lit-question').focus();
  };
  $('home-demo').onclick=async()=>{
    window.researchApp.open('literature');
    if(busy||importing||translating)return;
    try{
      const data=await getCatalog();
      if(document.body.dataset.screen!=='literature'||busy||importing||translating)return;
      desk.querySelector('[value="builtin"]').checked=true;scope();
      $('lit-question').value=data.example_question;
      await search();
    }catch(e){status(e.message,true);}
  };
  window.literatureDesk={entered(){scope();controls();getCatalog().catch(e=>status(e.message,true));}};
  scope();
})();
