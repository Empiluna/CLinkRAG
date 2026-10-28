/* Runtime configuration is saved by the local server, never in browser storage. */
(() => {
 const page=$('settings-screen');
 page.querySelector('.page-heading p').textContent='连接研究服务，调整你的阅读与使用习惯。';
 page.querySelector('.section-kicker').hidden=true;
 const preferences=document.createElement('section');preferences.id='settings-preferences';preferences.hidden=true;
 preferences.setAttribute('role','tabpanel');preferences.setAttribute('aria-labelledby','settings-tab-preferences');
 preferences.append(page.querySelector('.settings-grid'),$('settings-reset'));
 const shell=document.createElement('div');shell.className='model-settings';
 shell.innerHTML=`
 <nav class="settings-tabs" role="tablist" aria-label="设置分类">
   <button id="settings-tab-model" data-settings-tab="model" role="tab" aria-selected="true" aria-controls="settings-model">模型服务</button>
   <button id="settings-tab-retrieval" data-settings-tab="retrieval" role="tab" aria-selected="false" aria-controls="settings-retrieval" tabindex="-1">检索与重排</button>
   <button id="settings-tab-preferences" data-settings-tab="preferences" role="tab" aria-selected="false" aria-controls="settings-preferences" tabindex="-1">界面与默认值</button>
 </nav>
 <div id="model-settings-summary" class="model-summary"><span>读取运行配置…</span></div>
 <div id="model-settings-overrides" class="settings-notice" hidden></div>
 <form id="model-settings-form" novalidate>
 <section id="settings-model" role="tabpanel" aria-labelledby="settings-tab-model" class="runtime-settings-panel">
 <div class="settings-section-intro"><span class="settings-number">01</span><div><h2>为研究选择模型</h2><p>同一套模型配置用于问题分析、证据组织和回答生成。</p></div><span class="settings-tag">保存到本地服务</span></div>
 <div class="model-config-layout"><section class="panel settings-card runtime-card">
 <label for="ms-LLM_PROVIDER">模型服务</label><select id="ms-LLM_PROVIDER"><option value="anthropic">Claude · Anthropic 原生接口</option><option value="deepseek">DeepSeek · 官方服务</option><option value="openai">OpenAI · 官方服务</option><option value="qwen">通义千问 · 百炼北京</option><option value="openai_compatible">自定义 · OpenAI 兼容服务</option></select>
 <div class="service-preset-info"><div><strong id="preset-protocol"></strong><a id="preset-docs" target="_blank" rel="noopener noreferrer">官方模型与接口文档 ↗</a></div><p id="preset-note"></p><span id="preset-checked"></span></div>
 <label for="ms-model-preset">预设模型</label><select id="ms-model-preset"><option value="">自定义模型 ID</option></select><p class="field-hint">切换服务会填入该预设的地址与首选模型；你仍可修改下方字段。可选模型以服务账号的权限为准。</p>
 <label for="ms-MODEL_NAME">模型 ID <span>由服务商提供</span></label><input id="ms-MODEL_NAME" type="text" maxlength="512" required spellcheck="false" placeholder="填写服务实际支持的模型 ID"><p class="field-hint">必须支持文本对话与 JSON 输出；仅填写名称不会安装或开通模型。</p>
 <div id="ms-deepseek-url"><label for="ms-DEEPSEEK_BASE_URL">接口地址</label><input id="ms-DEEPSEEK_BASE_URL" type="url" required spellcheck="false"><p class="field-hint">填写接口根地址，不需要添加 /chat/completions。</p></div>
 <div id="ms-openai-url" hidden><label for="ms-OPENAI_BASE_URL">接口地址</label><input id="ms-OPENAI_BASE_URL" type="url" required spellcheck="false"><p class="field-hint">按服务文档填写完整前缀，可能包含 /v1；不添加 /chat/completions。</p></div>
 <div id="ms-anthropic-url" hidden><label for="ms-ANTHROPIC_BASE_URL">Claude 接口地址</label><input id="ms-ANTHROPIC_BASE_URL" type="url" required spellcheck="false"><p class="field-hint">官方地址为 https://api.anthropic.com；也接受以 /v1 结尾的原生协议网关地址，不添加 /messages。</p></div>
 <div id="ms-qwen-url" hidden><label for="ms-QWEN_BASE_URL">百炼 接口地址</label><input id="ms-QWEN_BASE_URL" type="url" required spellcheck="false"><p class="field-hint">预设为北京地域。接口地址需要与密钥地域一致，可替换为业务空间专属地址。</p></div>
 <div id="ms-deepseek-key"><label for="ms-DEEPSEEK_API_KEY">API 密钥 <span id="status-DEEPSEEK_API_KEY"></span></label><input id="ms-DEEPSEEK_API_KEY" type="password" autocomplete="new-password" spellcheck="false" placeholder="留空保留已保存的密钥"></div>
 <div id="ms-openai-key" hidden><label for="ms-OPENAI_API_KEY">API 密钥 <span id="status-OPENAI_API_KEY"></span></label><input id="ms-OPENAI_API_KEY" type="password" autocomplete="new-password" spellcheck="false" placeholder="留空保留已保存的密钥"></div>
 <div id="ms-anthropic-key" hidden><label for="ms-ANTHROPIC_API_KEY">Anthropic API 密钥 <span id="status-ANTHROPIC_API_KEY"></span></label><input id="ms-ANTHROPIC_API_KEY" type="password" autocomplete="new-password" spellcheck="false" placeholder="填写 Claude 服务的 API Key；留空保留"></div>
 <div id="ms-qwen-key" hidden><label for="ms-QWEN_API_KEY">百炼 API 密钥 <span id="status-QWEN_API_KEY"></span></label><input id="ms-QWEN_API_KEY" type="password" autocomplete="new-password" spellcheck="false" placeholder="填写北京地域 API Key；留空保留"></div>
 <p class="field-hint">仅在替换密钥时填写。密钥写入本机配置文件，不会回显或保存在浏览器偏好中。</p>
 </section><aside class="settings-context"><div class="settings-context-icon">↗</div><h3>先选服务，再填模型</h3><p>接口地址、模型 ID 和密钥需要属于同一个服务。切换接口类型时，会保留各自已填写的地址与密钥。</p><div class="settings-context-rule"></div><h4>怎样确认能运行？</h4><p>本地检查范围：参数、设备与模型文件。研究运行时连接所选 API。</p><h4>已运行的研究</h4><p>历史结果保持原样。新的研究会记录本次使用的非敏感模型配置，方便回溯。</p></aside></div>
 <details class="panel settings-card settings-advanced"><summary>高级请求参数 <span>超时、重试与思考模式</span></summary><div class="settings-field-grid"><div><label for="ms-REQUEST_TIMEOUT">请求超时 / 秒</label><input id="ms-REQUEST_TIMEOUT" type="number" min="10" max="600" step="1" required><p class="field-hint">单次模型请求的等待上限，10–600 秒。</p></div><div><label for="ms-MAX_RETRIES">最大重试次数</label><input id="ms-MAX_RETRIES" type="number" min="0" max="5" step="1" required><p class="field-hint">失败重试可能增加等待时间与请求费用。</p></div><div id="ms-thinking"><label for="ms-DEEPSEEK_THINKING">DeepSeek 思考参数</label><select id="ms-DEEPSEEK_THINKING"><option value="disabled">关闭 · disabled</option><option value="enabled">开启 · enabled</option><option value="omit">不发送该参数</option></select><p class="field-hint">仅用于支持 thinking 参数的接口；兼容接口不发送此参数。</p></div></div></details>
 </section>
 <section id="settings-retrieval" role="tabpanel" aria-labelledby="settings-tab-retrieval" class="runtime-settings-panel" hidden>
 <div class="settings-section-intro"><span class="settings-number">02</span><div><h2>让相关证据排在前面</h2><p>语义重排参数同时用于 CLinkRAG 和 SciRAG 的候选论文筛选。</p></div><span class="settings-tag">本地推理</span></div>
 <div class="model-config-layout"><section class="panel settings-card runtime-card">
 <label for="ms-RERANKER_MODEL">重排模型 ID / 本地模型目录</label><input id="ms-RERANKER_MODEL" type="text" required maxlength="512" spellcheck="false" list="reranker-examples"><datalist id="reranker-examples"><option value="BAAI/bge-reranker-v2-m3"></option><option value="BAAI/bge-reranker-base"></option><option value="BAAI/bge-reranker-large"></option></datalist><p class="field-hint">使用 FlagReranker 支持的编码器式模型；不支持在此填写生成模型或远程重排 API。</p>
 <label for="ms-RERANKER_DEVICE">推理设备</label><input id="ms-RERANKER_DEVICE" type="text" required list="reranker-devices" spellcheck="false" placeholder="cpu / cuda:0"><datalist id="reranker-devices"><option value="cpu">CPU</option><option value="cuda:0">第一张 NVIDIA GPU</option></datalist><p id="settings-device-hint" class="field-hint">执行本地检查可识别当前可用的 GPU。</p>
 <div class="settings-field-grid"><div><label for="ms-RERANKER_BATCH_SIZE">批量大小</label><input id="ms-RERANKER_BATCH_SIZE" type="number" min="1" max="64" step="1" required><p class="field-hint">同时评分的文本对数量。显存不足时调小。</p></div><div><label for="ms-RERANKER_MAX_LENGTH">文本长度上限 / tokens</label><input id="ms-RERANKER_MAX_LENGTH" type="number" min="128" max="8192" step="1" required><p class="field-hint">更长会增加内存占用；还需遵循所选模型的最大长度。</p></div></div>
 <label class="setting-check"><input id="ms-RERANKER_FP16" type="checkbox"> GPU 使用 FP16 半精度</label><p class="field-hint">降低显存占用；选择 CPU 时自动使用 FP32。</p>
 <label class="setting-check"><input id="ms-RERANKER_OFFLINE" type="checkbox">仅使用本地已有模型文件</label><p class="field-hint">关闭后允许首次研究从 Hugging Face 下载权重，可能需要较长时间与较大磁盘空间。本地检查不会下载模型。</p>
 </section><aside class="settings-context"><div class="settings-context-icon">⇅</div><h3>模型与设备各司其职</h3><p>LLM 负责理解与生成，重排模型负责给问题和文献片段评分。重排模型在这台电脑上运行，不使用 LLM API Key。</p><div class="settings-context-rule"></div><h4>切换模型前</h4><p>使用兼容的模型架构；本地目录需包含模型配置、分词器和权重。</p><h4>显存不足时</h4><p>先降低批量大小，再减少文本长度，或切换到 CPU。FP16 选项只对 GPU 生效。</p></aside></div>
 <section class="panel settings-card retrieval-service"><div><h3>Semantic Scholar 检索服务</h3><p class="field-hint">用于 CLinkRAG 与 SciRAG 在线检索。固定资料库模式无需调用该服务。</p></div><div><label for="ms-S2_API_KEY">检索 API 密钥 <span id="status-S2_API_KEY"></span></label><input id="ms-S2_API_KEY" type="password" autocomplete="new-password" placeholder="留空保留已有密钥" spellcheck="false"></div></section>
 </section>
 <section id="settings-check-results" class="panel settings-check-results" aria-live="polite" hidden></section>
 <div id="runtime-settings-actions" class="runtime-settings-actions"><div><strong id="runtime-save-state" role="status">正在加载…</strong><p id="runtime-save-detail">运行配置需手动保存；研究进行中不能修改。</p></div><div class="settings-action-buttons"><button id="runtime-reload" type="button" class="text-button">重新加载</button><button id="runtime-check" type="button" class="secondary" disabled>本地检查</button><button id="runtime-save" type="submit" class="primary" disabled>保存更改</button></div></div>
 </form>`;
 page.append(shell);shell.append(preferences);
 // Group by the user's task while preserving the existing controls and their values.
 const tabDefinitions=[
  ['model','回答模型','理解问题与生成正文','M4 5h16v12H9l-5 4V5Zm4 4h8M8 13h5'],
  ['search','论文检索','连接学术文献来源','M10 17a7 7 0 1 0 0-14 7 7 0 0 0 0 14Zm5-2 6 6'],
  ['retrieval','论文排序','挑选更相关的材料','M5 5h14M5 12h10M5 19h6m8-10v12m-3-3 3 3 3-3'],
  ['preferences','阅读偏好','外观与新研究默认值','M4 4h7v16H4Zm9 0h7v16h-7M7 8h1m8 0h1']
 ];
 const settingsNav=shell.querySelector('.settings-tabs');
 for(const [key,title,description,path] of tabDefinitions){
  let button=$('settings-tab-'+key);
  if(!button){button=document.createElement('button');button.id='settings-tab-'+key;button.type='button';button.dataset.settingsTab=key;button.setAttribute('role','tab');button.setAttribute('aria-controls','settings-'+key);}
  button.innerHTML=`<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${path}"/></svg><span><b>${title}</b><small>${description}</small></span>`;
  button.setAttribute('aria-label',title);button.setAttribute('aria-description',description);settingsNav.append(button);
 }
 function cardHeading(card,title,description){const heading=document.createElement('div');heading.className='settings-card-heading';heading.innerHTML=`<h3>${title}</h3><p>${description}</p>`;card.prepend(heading);}
 const modelLayout=$('settings-model').querySelector('.model-config-layout');
 const modelCard=modelLayout.querySelector('.runtime-card');
 const connectionCard=document.createElement('section');connectionCard.className='panel settings-card runtime-card';
 let connectionField=$('ms-deepseek-url');
 while(connectionField){const next=connectionField.nextSibling;connectionCard.append(connectionField);connectionField=next;}
 modelLayout.querySelector('.settings-context').remove();modelLayout.append(connectionCard);
 cardHeading(modelCard,'选择模型','先选服务，再选用于研究的模型。');
 cardHeading(connectionCard,'连接服务','填写所选服务的接口地址与密钥。');
 const presetDetails=document.createElement('details');presetDetails.className='service-preset-details';
 presetDetails.innerHTML='<summary>接口说明与官方文档</summary>';
 presetDetails.append(modelCard.querySelector('.service-preset-info'));modelCard.append(presetDetails);
 $('settings-model').querySelector('.settings-section-intro').remove();
 const searchPanel=document.createElement('section');searchPanel.id='settings-search';searchPanel.hidden=true;searchPanel.className='runtime-settings-panel';searchPanel.setAttribute('role','tabpanel');searchPanel.setAttribute('aria-labelledby','settings-tab-search');
 const service=$('settings-retrieval').querySelector('.retrieval-service');
 service.querySelector('h3').textContent='Semantic Scholar';
 service.querySelector('p').textContent='为研究查找学术论文、摘要与引用信息。';
 searchPanel.append(service);
 const searchNote=document.createElement('div');searchNote.className='settings-inline-note';searchNote.textContent='每次研究的论文篇数、检索方向和补充搜索次数，可在首页的“更多设置”中调整。';searchPanel.append(searchNote);
 $('settings-model').after(searchPanel);
 const rerankPanel=$('settings-retrieval');rerankPanel.querySelector('.settings-section-intro').remove();rerankPanel.querySelector('.settings-context').remove();
 const rerankCard=rerankPanel.querySelector('.runtime-card');
 const performance=document.createElement('details');performance.className='panel settings-card settings-advanced';performance.innerHTML='<summary>性能与模型文件 <span>批量大小、文本长度与运行精度</span></summary><div class="settings-advanced-body"></div>';
 let performanceField=rerankCard.querySelector('.settings-field-grid');
 while(performanceField){const next=performanceField.nextSibling;performance.lastElementChild.append(performanceField);performanceField=next;}
 cardHeading(rerankCard,'按相关程度挑选论文','在本机给候选材料排序，把更相关的证据排在前面。');
 rerankPanel.append(performance);
 const overrides=$('model-settings-overrides');$('settings-model').querySelector('.settings-advanced').append(overrides);
 preferences.insertAdjacentHTML('afterbegin','<div class="settings-inline-note">这里的偏好自动保存在当前浏览器。</div>');
 // Keep the field explanations concise; implementation detail stays in disclosures.
 modelCard.querySelectorAll('.field-hint')[0].textContent='预设会填入模型 ID，也可以在下方手动修改。';
 modelCard.querySelectorAll('.field-hint')[1].textContent='填写服务商提供的模型 ID。';
 connectionCard.querySelector(':scope > .field-hint').textContent='密钥仅在替换时填写，留空保留已保存的密钥。';
 $('ms-RERANKER_MODEL').nextElementSibling.nextElementSibling.textContent='支持 BGE 重排模型 ID，或已下载模型的本地目录。';

 let loaded=null,loading=false,dirty=false,busy=false,active='model';
 const profileManager=document.createElement('section');profileManager.className='saved-models panel settings-card';
 profileManager.innerHTML='<div class="saved-models-heading"><div><h3>模型商与模型</h3><p>每个模型商配置一次，勾选的模型会出现在首页。</p></div><button id="profile-add" type="button" class="secondary">＋ 添加模型商</button></div><div id="profile-list"></div><p id="profile-support-note" class="field-hint" hidden></p>';
 $('settings-model').prepend(profileManager);
 // Keep legacy fields bound for runtime saves; connection editing now lives in the provider dialog.
 $('settings-model').querySelector('.model-config-layout').hidden=true;
 $('settings-model').querySelector('.model-config-layout').style.display='none';
 const profileDialog=document.createElement('dialog');profileDialog.id='model-profile-dialog';profileDialog.setAttribute('aria-labelledby','profile-title');
 profileDialog.innerHTML=`<form id="profile-form"><header><div><h2 id="profile-title">添加模型商</h2><p>连接服务，再选择要在首页使用的模型。</p></div><button type="button" id="profile-close" class="icon-button" aria-label="关闭模型商设置">×</button></header>
 <div class="profile-fields"><details class="provider-connection" id="provider-connection"><summary>连接设置 <span>接口地址与 API 密钥</span></summary><div class="provider-connection-grid"><div><label for="profile-name">模型商名称</label><input id="profile-name" maxlength="80" required placeholder="例如：DeepSeek" autocomplete="off"></div><div><label for="profile-provider">接口类型</label><select id="profile-provider"></select></div></div>
 <label for="profile-url">接口地址</label><input id="profile-url" type="url" required spellcheck="false" placeholder="https://…">
 <label for="profile-key">API 密钥 <span id="profile-key-status"></span></label><input id="profile-key" type="password" autocomplete="new-password" maxlength="4096" spellcheck="false"><p class="field-hint">同一模型商的模型共用此连接，密钥仅保存在本机。</p></details>
 <section class="provider-model-selection" aria-labelledby="provider-models-heading"><div class="provider-model-toolbar"><div><h3 id="provider-models-heading">首页可选模型</h3><p id="provider-model-count">已选 0 个</p></div><button type="button" id="provider-model-refresh" class="secondary"><span class="model-refresh-spinner" aria-hidden="true"></span><span>读取模型列表</span></button></div>
 <p id="provider-catalog-message" role="status"></p><div id="provider-model-options"></div>
 <details class="provider-manual"><summary>手动添加模型 ID</summary><div><input id="provider-model-id" maxlength="512" aria-label="手动添加模型 ID" placeholder="填写服务商提供的模型 ID" spellcheck="false"><button type="button" id="provider-model-add" class="secondary">添加</button></div></details></section>
 <p id="profile-error" role="alert" hidden></p></div>
 <footer><button type="button" id="profile-remove" class="text-button" hidden>移除模型商</button><div><button type="button" id="profile-cancel" class="secondary">取消</button><button id="profile-save" type="submit" class="primary">保存选择</button></div></footer></form>`;
 document.body.append(profileDialog);
 let editingService=null,chosenModels=new Set(),availableModels=new Map(),serviceLoading=false,serviceTicket=0;
 function renderProfiles(data){
  const list=$('profile-list');list.replaceChildren();
  $('profile-add').disabled=!data.service_support||busy;
  $('profile-support-note').hidden=!!data.service_support;$('profile-support-note').textContent='重启本地服务后即可按模型商管理模型。';
  for(const service of data.services||[]){
   const card=document.createElement('section');card.className='provider-card';
   const row=document.createElement('div');row.className='saved-model-row';
   const icon=document.createElement('span');icon.className='saved-model-icon';icon.textContent=service.name.slice(0,1).toUpperCase();icon.setAttribute('aria-hidden','true');
   const info=document.createElement('div');info.className='saved-model-info';
   const name=document.createElement('strong');name.textContent=service.name;
   const meta=document.createElement('small');meta.textContent=service.base_url;info.append(name,meta);row.append(icon,info);
   const actions=document.createElement('div');actions.className='saved-model-actions';
   const edit=document.createElement('button');edit.type='button';edit.className='secondary';edit.textContent='管理模型';edit.disabled=busy;edit.setAttribute('aria-label','管理模型：'+service.name);edit.onclick=()=>openProfile(service);actions.append(edit);row.append(actions);card.append(row);
   const models=document.createElement('div');models.className='provider-selected-models';
   for(const model of service.models){const chip=document.createElement('span');chip.className='provider-model-chip'+(model.active?' is-current':'');chip.textContent=model.model;if(model.active){const badge=document.createElement('small');badge.textContent='当前使用';chip.append(badge);}models.append(chip);}card.append(models);list.append(card);
  }
 }
 function connectionDraft(){return {id:editingService?.id,name:$('profile-name').value.trim(),provider:$('profile-provider').value,base_url:$('profile-url').value.trim(),api_key:$('profile-key').value};}
 function updateProfileKeyHint(){
  const retained=editingService?.configured&&editingService.provider===$('profile-provider').value&&editingService.base_url.replace(/\/$/,'')===$('profile-url').value.trim().replace(/\/$/,'');
  $('profile-key-status').textContent=retained?'已保存':'';$('profile-key').placeholder=retained?'留空保留此模型商的密钥':'填写这个模型商的 API 密钥';$('profile-key').required=!retained;
 }
 function renderModelChoices(){
  const list=$('provider-model-options');list.replaceChildren();
  for(const [id,name] of availableModels){
   const label=document.createElement('label');label.className='provider-model-choice';
   const check=document.createElement('input');check.type='checkbox';check.value=id;check.checked=chosenModels.has(id);check.disabled=busy||serviceLoading;
   const text=document.createElement('span');const title=document.createElement('strong');title.textContent=name||id;text.append(title);if(name&&name!==id){const sub=document.createElement('small');sub.textContent=id;text.append(sub);}
   check.onchange=()=>{if(check.checked)chosenModels.add(id);else chosenModels.delete(id);$('provider-model-count').textContent=`已选 ${chosenModels.size} 个 · 保存后显示在首页`;};label.append(check,text);list.append(label);
  }
  if(!availableModels.size){const empty=document.createElement('p');empty.className='provider-model-empty';empty.textContent='读取此接口的模型列表，然后勾选你想使用的模型。';list.append(empty);}
  $('provider-model-count').textContent=`已选 ${chosenModels.size} 个 · 保存后显示在首页`;
 }
 function openProfile(service=null){
  if(busy||!loaded?.service_support)return;
  if(dirty){toast('请先保存当前页面的更改，再管理模型商。');return;}
  serviceTicket++;serviceLoading=false;editingService=service;$('profile-form').reset();$('profile-error').hidden=true;
  $('profile-title').textContent=service?'管理模型商':'添加模型商';
  const select=$('profile-provider');select.replaceChildren();for(const p of loaded.presets)select.append(new Option(p.name,p.id));select.value=service?.provider||loaded.values.LLM_PROVIDER;
  const preset=loaded.presets.find(p=>p.id===select.value);$('profile-name').value=service?.name||preset?.name||'';$('profile-url').value=service?.base_url||preset?.base_url||'';
  chosenModels=new Set((service?.models||[]).map(m=>m.model));availableModels=new Map((service?.models||[]).map(m=>[m.model,m.name]));
  $('provider-catalog-message').textContent=service?'已保存的模型已勾选；读取列表可以选择更多模型。':'';
  $('profile-remove').hidden=!service||service.models.some(m=>m.active);$('provider-connection').open=!service;updateProfileKeyHint();renderModelChoices();controls();profileDialog.showModal();(service?$('provider-model-refresh'):$('profile-name')).focus();
 }
 function connectionEdited(){serviceTicket++;serviceLoading=false;chosenModels.clear();availableModels.clear();$('provider-catalog-message').textContent='连接已变更，请重新读取模型列表。';updateProfileKeyHint();renderModelChoices();controls();}
 $('profile-add').onclick=()=>openProfile();
 $('profile-provider').onchange=()=>{const p=loaded.presets.find(p=>p.id===$('profile-provider').value);$('profile-name').value=p?.name||'';$('profile-url').value=p?.base_url||'';$('profile-key').value='';connectionEdited();};
 $('profile-url').oninput=connectionEdited;$('profile-key').oninput=connectionEdited;
 $('provider-model-add').onclick=()=>{const id=$('provider-model-id').value.trim();if(!id)return;if(id.length>512||/[\x00-\x1f]/.test(id)){toast('请填写有效的模型 ID');return;}availableModels.set(id,id);chosenModels.add(id);$('provider-model-id').value='';renderModelChoices();};
 $('provider-model-id').onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();$('provider-model-add').click();}};
 $('provider-model-refresh').onclick=async()=>{
  if(serviceLoading||busy)return;
  for(const id of ['profile-provider','profile-url','profile-key'])if(!$(id).checkValidity()){$('provider-connection').open=true;$(id).reportValidity();return;}
  const ticket=++serviceTicket;serviceLoading=true;controls();$('provider-catalog-message').textContent='正在读取模型列表…';
  try{const result=await api('/api/models',{method:'POST',body:JSON.stringify({refresh:true,service:connectionDraft()})});if(ticket!==serviceTicket)return;
   if(result.source==='api'){availableModels=new Map([...availableModels].filter(([id])=>chosenModels.has(id)));for(const m of result.models)availableModels.set(m.id,m.name);$('provider-catalog-message').textContent=`接口返回 ${result.models.length} 个模型，请勾选要在首页使用的模型。`;}
   else $('provider-catalog-message').textContent=(result.message||'暂时未取得模型列表。')+' 已有选择保留，也可以手动添加模型 ID。';
  }catch(error){if(ticket===serviceTicket)$('provider-catalog-message').textContent=error.message;}
  finally{if(ticket===serviceTicket){serviceLoading=false;renderModelChoices();controls();}}
 };
 for(const id of ['profile-close','profile-cancel'])$(id).onclick=()=>{if(!busy)profileDialog.close();};
 profileDialog.addEventListener('cancel',e=>{if(busy)e.preventDefault();});profileDialog.addEventListener('close',()=>{serviceTicket++;serviceLoading=false;$('profile-key').value='';editingService=null;controls();});
 async function profileMutation(payload){
  if(busy||!loaded?.service_support)return false;
  if(dirty){toast('请先保存当前页面的更改。');return false;}
  busy=true;controls();$('profile-error').hidden=true;
  try{const saved=await api('/api/settings',{method:'POST',body:JSON.stringify({revision:loaded.revision,...payload})});render(saved);await connect();return true;}
  catch(error){if(profileDialog.open){$('profile-error').textContent=error.message;$('profile-error').hidden=false;}else toast(error.message);return false;}
  finally{busy=false;controls();renderProfiles(loaded);renderHomeModels(loaded);}
 }
 async function activateProfile(id){if(await profileMutation({profile_action:'activate',profile_id:id}))toast('已切换研究模型');}
 $('profile-form').onsubmit=async e=>{e.preventDefault();if(serviceLoading)return;if(!chosenModels.size){$('profile-error').textContent='请至少选择一个模型。';$('profile-error').hidden=false;return;}if(await profileMutation({service_action:'save',service:{...connectionDraft(),models:[...chosenModels]}})){profileDialog.close();toast('已保存，首页仅显示选中的模型。');}};
 $('profile-remove').onclick=async()=>{if(!editingService||busy||!confirm('移除模型商“'+editingService.name+'”及其模型配置？已有研究记录会保留。'))return;if(await profileMutation({service_action:'delete',service_id:editingService.id})){profileDialog.close();toast('模型商已移除');}};

 const secretKeys=['OPENAI_API_KEY','DEEPSEEK_API_KEY','ANTHROPIC_API_KEY','QWEN_API_KEY','S2_API_KEY'];
 const integerKeys=['REQUEST_TIMEOUT','MAX_RETRIES','RERANKER_BATCH_SIZE','RERANKER_MAX_LENGTH'];
 function tab(name){active=name;for(const key of tabDefinitions.map(item=>item[0])){const selected=key===name;$('settings-'+key).hidden=!selected;const button=$('settings-tab-'+key);button.setAttribute('aria-selected',String(selected));button.tabIndex=selected?0:-1;}$('model-settings-form').hidden=name==='preferences';$('model-settings-summary').hidden=name==='preferences';$('model-settings-overrides').hidden=name==='preferences'||!loaded?.environment_overrides?.length;}
 const tabs=[...shell.querySelectorAll('[data-settings-tab]')];tabs.forEach((button,index)=>{button.onclick=()=>tab(button.dataset.settingsTab);button.onkeydown=e=>{let next=index;if(e.key==='ArrowRight')next=(index+1)%tabs.length;else if(e.key==='ArrowLeft')next=(index+tabs.length-1)%tabs.length;else if(e.key==='Home')next=0;else if(e.key==='End')next=tabs.length-1;else return;e.preventDefault();tabs[next].click();tabs[next].focus();};});
 function message(text,detail,error=false){$('runtime-save-state').textContent=text;$('runtime-save-state').classList.toggle('settings-error',error);if(detail)$('runtime-save-detail').textContent=detail;}
 function controls(){for(const e of profileDialog.querySelectorAll('input,select,button'))e.disabled=busy||(serviceLoading&&!['profile-close','profile-cancel'].includes(e.id));$('provider-model-refresh').classList.toggle('is-loading',serviceLoading);$('provider-model-refresh').lastElementChild.textContent=serviceLoading?'读取中…':'读取模型列表';$('provider-model-options').setAttribute('aria-busy',String(serviceLoading));$('profile-add').disabled=busy||!loaded?.service_support;for(const e of profileManager.querySelectorAll('.saved-model-actions button'))e.disabled=busy||e.dataset.unconfigured==='true';if($('home-model')){$('home-model').disabled=busy||!loaded;$('home-model-toggle').disabled=busy||!loaded||(!loaded.llm_configured&&!(loaded.profiles||[]).some(p=>p.configured));}for(const id of ['runtime-save','runtime-check'])$(id).disabled=busy||!loaded||(id==='runtime-save'&&!dirty);$('runtime-reload').disabled=busy||loading;for(const element of $('model-settings-form').querySelectorAll('input,select')){const key=element.id.replace('ms-','');element.disabled=busy||!loaded||(loaded.environment_overrides||[]).includes(key)||(element.id==='ms-model-preset'&&(loaded.environment_overrides||[]).includes('MODEL_NAME'));}}
 function preset(){return loaded?.presets?.find(item=>item.id===$('ms-LLM_PROVIDER').value);}
 function providerFields(){const selected=$('ms-LLM_PROVIDER').value;const group=['anthropic','qwen','deepseek'].includes(selected)?selected:'openai';for(const key of ['deepseek','openai','anthropic','qwen'])for(const suffix of ['url','key'])$('ms-'+key+'-'+suffix).hidden=key!==group;$('ms-thinking').hidden=selected!=='deepseek';
 const item=preset();$('preset-protocol').textContent=item?.protocol||'自定义服务';$('preset-note').textContent=item?.note||'';const link=$('preset-docs');link.hidden=!item?.docs;if(item?.docs)link.href=item.docs;$('preset-checked').textContent=loaded?.presets_checked_at?'预设核对日期：'+loaded.presets_checked_at:'';
 const select=$('ms-model-preset');select.replaceChildren();const groups=new Map();for(const model of item?.models||[]){const option=document.createElement('option');option.value=model.id;option.textContent=model.name+' · '+model.id;let parent=select;if(model.group){if(!groups.has(model.group)){const group=document.createElement('optgroup');group.label=model.group;groups.set(model.group,group);select.append(group);}parent=groups.get(model.group);}parent.append(option);}const custom=document.createElement('option');custom.value='';custom.textContent='自定义模型 ID';select.append(custom);select.value=(item?.models||[]).some(model=>model.id===$('ms-MODEL_NAME').value)?$('ms-MODEL_NAME').value:'';}
 function applyPreset(){const item=preset();if(item?.base_url&&!loaded.environment_overrides.includes(item.url_key))$("ms-"+item.url_key).value=item.base_url;if(item?.models?.length&&!loaded.environment_overrides.includes('MODEL_NAME'))$('ms-MODEL_NAME').value=item.models[0].id;providerFields();}
 function values(){return Object.fromEntries(Object.keys(loaded.values).map(key=>{const element=$('ms-'+key);return [key,element.type==='checkbox'?element.checked:integerKeys.includes(key)?Number(element.value):element.value.trim()];}));}
 function changed(){if(!loaded)return;dirty=JSON.stringify(values())!==JSON.stringify(loaded.values)||secretKeys.some(key=>$('ms-'+key).value.length);message(dirty?'有未保存的运行配置':'与本地配置一致','保存后用于下一次研究。界面偏好仍会自动保存。');$('settings-check-results').hidden=true;providerFields();controls();}
 function render(data){loaded=data;renderProfiles(data);renderHomeModels(data);for(const [key,value]of Object.entries(data.values)){const element=$('ms-'+key);if(!element)continue;if(element.type==='checkbox')element.checked=value;else element.value=value;}for(const key of secretKeys){$('ms-'+key).value='';$('status-'+key).textContent=data.credentials[key]?'已配置 · 留空保留':'未配置';}
 const summary=$('model-settings-summary');summary.replaceChildren();for(const [name,value]of [['回答模型',data.values.MODEL_NAME],['排序模型',data.values.RERANKER_MODEL],['运行设备',data.values.RERANKER_DEVICE]]){const item=document.createElement('div');const label=document.createElement('span');label.textContent=name;const strong=document.createElement('strong');strong.textContent=value;item.append(label,strong);summary.append(item);}const note=$('model-settings-overrides');note.textContent=data.environment_overrides.length?'环境变量优先：'+data.environment_overrides.join('、')+'。被覆盖的字段不能在此更改。':'';note.hidden=!data.environment_overrides.length;dirty=false;providerFields();message('与本地配置一致','运行配置需手动保存；研究进行中不能修改。');controls();tab(active);}
 async function load(){if(loading||busy)return;loading=true;$('runtime-reload').disabled=true;try{render(await api('/api/settings'));$('settings-check-results').hidden=true;}catch(error){message('无法读取运行配置',error.message,true);}finally{loading=false;controls();}}
 function validForm(){if(!loaded)return false;for(const field of $('model-settings-form').querySelectorAll('input')){if(!field.checkValidity()){const panel=field.closest('[role=tabpanel]');if(panel)tab(panel.id.replace('settings-',''));const details=field.closest('details');if(details)details.open=true;field.reportValidity();return false;}}return true;}
 $('model-settings-form').addEventListener('input',event=>{if(!['ms-LLM_PROVIDER','ms-model-preset'].includes(event.target.id))changed();});$('model-settings-form').addEventListener('change',event=>{if(event.target.id==='ms-LLM_PROVIDER')applyPreset();if(event.target.id==='ms-model-preset'){$('ms-MODEL_NAME').value=event.target.value;if(!event.target.value)$('ms-MODEL_NAME').focus();}changed();});
 $('runtime-reload').onclick=()=>{if(dirty&&!confirm('重新加载会放弃尚未保存的模型配置，继续吗？'))return;load();};
 $('model-settings-form').onsubmit=async event=>{event.preventDefault();if(busy||!dirty||!validForm())return;const payload={revision:loaded.revision,values:values(),secrets:Object.fromEntries(secretKeys.map(key=>[key,$('ms-'+key).value]))};busy=true;controls();message('正在保存…');try{render(await api('/api/settings',{method:'POST',body:JSON.stringify(payload)}));message('运行配置已保存','下一次研究将使用此配置；保存没有发送模型请求。');await connect();}catch(error){message('未保存',error.message,true);}finally{busy=false;controls();}};
 $('runtime-check').onclick=async()=>{if(busy||!validForm())return;const draft=values();busy=true;controls();message('正在检查本地环境…','不会调用付费模型，也不会下载权重。');try{const result=await api('/api/settings/check',{method:'POST',body:JSON.stringify({values:draft})});const box=$('settings-check-results');box.replaceChildren();const heading=document.createElement('h3');heading.textContent='本地检查结果 · 当前表单';box.append(heading);for(const row of result.checks){const item=document.createElement('div');item.className='settings-check-row '+row.status;const icon=document.createElement('span');icon.textContent=row.status==='ok'?'✓':row.status==='error'?'×':'!';const text=document.createElement('div');const title=document.createElement('strong');title.textContent=row.title;const detail=document.createElement('p');detail.textContent=row.detail;text.append(title,detail);item.append(icon,text);box.append(item);}const options=$('reranker-devices');options.replaceChildren();for(const device of result.devices){const option=document.createElement('option');option.value=device.id;option.textContent=device.name;options.append(option);}$('settings-device-hint').textContent='检测到：'+result.devices.map(d=>d.id+' · '+d.name).join('；');box.hidden=false;message(result.checks.some(row=>row.status==='error')?'检查发现需处理的项目':'本地检查完成','未验证远程 API、未加载重排模型；检查不会保存表单。');}catch(error){message('检查未完成',error.message,true);}finally{busy=false;controls();}};
 // The homepage is a picker for saved choices, not the provider's full API directory.
 const homeModel=$('home-model');
 const modelToggle=$('home-model-toggle'),modelList=$('home-model-list'),modelMenu=$('home-model-menu');
 let catalogLoading=false;
 const modelRefresh=$('home-model-refresh');
 modelRefresh.innerHTML='<span class="model-refresh-spinner" aria-hidden="true"></span><span class="model-refresh-label">刷新</span>';
 modelRefresh.setAttribute('aria-live','polite');
 function closeModelList(focus=false){modelMenu.hidden=true;modelToggle.setAttribute('aria-expanded','false');if(focus)modelToggle.focus();}
 function renderHomeModels(data){
  modelRefresh.setAttribute('aria-disabled',String(catalogLoading||busy));modelRefresh.classList.toggle('is-loading',catalogLoading);
  modelRefresh.querySelector('.model-refresh-label').textContent=catalogLoading?'刷新中':'刷新';modelList.setAttribute('aria-busy',String(catalogLoading));
  if(catalogLoading)return;
  const focused=modelList.contains(document.activeElement)?document.activeElement.dataset.profile:null;
  homeModel.replaceChildren();modelList.replaceChildren();
  const saved=(data.profiles||[]).filter(p=>p.configured),current=saved.find(p=>p.active);
  $('home-model-name').textContent=current?.name||'未配置模型';
  const groups=data.services||[];
  for(const service of groups){const models=service.models.filter(p=>p.configured);if(!models.length)continue;
   const heading=document.createElement('div');heading.className='home-model-group';heading.textContent=service.name;heading.setAttribute('role','presentation');modelList.append(heading);
   for(const profile of models){homeModel.append(new Option(profile.name,profile.id));const option=document.createElement('button');option.type='button';option.dataset.profile=profile.id;option.setAttribute('role','option');option.setAttribute('aria-selected',String(profile.active));option.className='home-profile-option';
    const name=document.createElement('span');name.textContent=profile.name;option.append(name);if(profile.active){const mark=document.createElement('span');mark.textContent='✓';mark.className='model-selected-mark';option.append(mark);}option.disabled=busy;option.onclick=()=>{closeModelList(true);if(!profile.active)activateProfile(profile.id);};modelList.append(option);
   }
  }
  homeModel.value=current?.id||'';$('home-model-count').textContent=saved.length+' 个已选模型';
  $('home-model-status').textContent=saved.length?'':'请在设置中添加模型商并选择模型。';$('home-model-status').hidden=!!saved.length;
  if(focused&&!modelMenu.hidden)([...modelList.children].find(e=>e.dataset.profile===focused)||modelRefresh).focus();
 }
 async function refreshSavedModels(){if(catalogLoading||busy||!token)return;if(dirty){toast('请先保存设置页中的更改。');return;}catalogLoading=true;renderHomeModels(loaded);try{render(await api('/api/settings'));}catch(error){toast(error.message);}finally{catalogLoading=false;renderHomeModels(loaded);}}
 modelToggle.onclick=()=>{const opening=modelMenu.hidden;modelMenu.hidden=!opening;modelToggle.setAttribute('aria-expanded',String(opening));if(opening)modelList.querySelector('[role=option]')?.focus();};
 modelRefresh.onclick=event=>{event.stopPropagation();refreshSavedModels();};
 modelToggle.onkeydown=e=>{if(e.key==='ArrowDown'){e.preventDefault();if(modelMenu.hidden)modelToggle.click();}};
 modelMenu.onkeydown=e=>{if(e.key==='Escape'){e.preventDefault();e.stopPropagation();closeModelList(true);}if(['ArrowDown','ArrowUp','Home','End'].includes(e.key)){const options=[...modelList.querySelectorAll('button:not(:disabled)')];if(!options.length)return;e.preventDefault();let i=options.indexOf(document.activeElement);i=e.key==='Home'?0:e.key==='End'?options.length-1:(i+(e.key==='ArrowDown'?1:-1)+options.length)%options.length;options[i].focus();}};
 // A render can temporarily drop focus onto the document. That is not a dismissal.
 // Inspect the original pointer path before any handler replaces menu contents.
 const modelPicker=modelToggle.closest('.home-model-picker');
 document.addEventListener('pointerdown',event=>{
  if(!modelMenu.hidden&&!event.composedPath().includes(modelPicker))closeModelList();
 },true);
 modelPicker.addEventListener('keydown',event=>{
  if(event.key!=='Tab')return;
  setTimeout(()=>{const target=document.activeElement;if(!modelMenu.hidden&&target&&target!==document.body&&target!==document.documentElement&&!modelPicker.contains(target))closeModelList();},0);
 });
 homeModel.onchange=()=>{if(homeModel.value)activateProfile(homeModel.value);};
 window.modelSettings={entered(){if(!loaded&&!loading)load();},isBusy(){return busy;}};
 window.addEventListener('beforeunload',event=>{if(dirty){event.preventDefault();event.returnValue='';}});
 tab('model');load();
})();
