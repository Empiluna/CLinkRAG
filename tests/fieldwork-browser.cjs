/* Isolated loopback server with temporary run storage; no personal history or paid requests. */
const fs=require('node:fs'), path=require('node:path');
const {spawn}=require('node:child_process');
const assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const root=path.resolve(__dirname,'..'), shots=process.env.UI_SCREENSHOTS;
const script=[
  'import tempfile',
  'from pathlib import Path',
  'from http.server import ThreadingHTTPServer',
  'from debug_ui.server import Jobs, make_handler',
  'from debug_ui.model_settings import DEFAULTS, SettingsStore',
  'with tempfile.TemporaryDirectory() as folder:',
  '    jobs=Jobs(Path(folder))',
  "    settings=SettingsStore(Path(folder)/'settings.yaml',loader=lambda: dict(DEFAULTS))",
  "    server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(jobs,'ui-test-session',settings))",
  '    print(server.server_port,flush=True)',
  '    server.serve_forever()'
].join('\n');

async function main(){
  const proc=spawn(process.env.PYTHON||'python',['-c',script],{cwd:root,windowsHide:true});
  let browser, stderr='';
  proc.stderr.on('data',chunk=>stderr+=chunk);
  try {
    const port=await new Promise((resolve,reject)=>{
      const timer=setTimeout(()=>reject(new Error('Test server did not start: '+stderr)),12000);
      proc.once('error',error=>{clearTimeout(timer);reject(error);});
      proc.once('exit',()=>{clearTimeout(timer);reject(new Error(stderr));});
      proc.stdout.once('data',data=>{clearTimeout(timer);resolve(Number(String(data).trim()));});
    });
    browser=await chromium.launch({channel:process.env.BROWSER_CHANNEL||'msedge',headless:true});
    const page=await browser.newPage({viewport:{width:1366,height:850},acceptDownloads:true});
    page.setDefaultTimeout(9000);
    const base='http://127.0.0.1:'+port;
    const errors=[],checks=[];
    const ok=(name,value)=>{assert.ok(value,name);checks.push(name);};
    const shot=async name=>{if(shots){fs.mkdirSync(shots,{recursive:true});await page.screenshot({path:path.join(shots,name+'.png'),animations:'disabled'});}};
    const $=id=>page.locator('#'+id);
    const external=[];
    page.on('request',r=>{if(/^https?:/.test(r.url()) && new URL(r.url()).origin!==base)external.push(r.url());});
    async function editQuery(){
      if(!await $('lit-query-panel').evaluate(node=>node.open))await $('lit-query-summary').click();
    }
    page.on('pageerror',e=>errors.push(e.message));
    let deep=false, allowBrief=false, sent=0, checkedItems;
    const fixture={id:'ab'.repeat(16),question:'城市绿地如何影响夏季地表温度？',method:'clinkrag_online',status:'success',created_at:'2026-01-01T10:00:00Z',elapsed_seconds:5};
    const study={answer:'## 研究发现\n林冠覆盖率与地表温度相关。[0]\n\n## 适用范围\n分析只涵盖样区。',evidence_review:'原文来自样区研究。[0]',sources:[{id:'cd'.repeat(20),title:'Study of urban canopy temperature',text:'Canopy temperature varied across the observed sites.',passage_id:'obs'}]};
    const paper=study.sources[0], neighbor={id:'de'.repeat(20),title:'Street shade in summer',url:'https://example.org/papers/shade'};
    const graph={nodes:[
      {...paper,cited:true,context:true,seed:true,retrieved:true,passages:[{id:'obs',text:paper.text}]},
      {...neighbor,context:true,retrieved:true,passages:[{id:'shade',text:'Street shade affected the pavement temperature.'}]}
    ],edges:[{id:'c1',source:paper.id,target:neighbor.id,type:'citation',weight:1,directed:true}]};
    await page.route('**/api/config',r=>r.fulfill({json:{token:'ui-test-session',capabilities:{deep_research:deep,resume:true},llm_configured:allowBrief,s2_configured:deep,model:allowBrief?'测试模型':''}}));
    await page.route('**/api/runs',r=>{
      if(r.request().method()==='POST'){sent++;return r.fulfill({status:400,json:{error:'Blocked paid generation in browser test'}});}
      return r.fulfill({json:[fixture]});
    });
    await page.route('**/api/runs/'+fixture.id+'?*',r=>r.fulfill({json:{run:fixture,events:[],result:study}}));
    await page.route('**/api/runs/'+fixture.id+'/graph',r=>r.fulfill({json:graph}));
    await page.route('**/api/models',r=>r.fulfill({json:{models:[]}}));
    await page.route('**/api/literature/terms',r=>{
      assert.deepEqual(Object.keys(r.request().postDataJSON()),['question']);
      return r.fulfill({json:{english_query:'urban heat shade'}});
    });
    await page.route('**/api/literature/brief',r=>{
      const body=r.request().postDataJSON();checkedItems=body.items;
      const quote=body.items[0].quote.split(' ').slice(1,6).join(' ');
      return r.fulfill({json:{findings:[{claim:'根据所选原句整理。',paper_id:body.items[0].paper_id,quote}],limitations:'仅限当前资料。',model:'测试模型',markdown:'研究发现'}});
    });
    await page.goto(base);
    await page.waitForSelector('#connection-state[data-state="online"]');
    await $('home-demo').waitFor();
    await shot('home-lite');
    ok('lightweight home points to source verification',await $('home-setup').isVisible()&&await $('home-setup').innerText().then(t=>t.includes('在线研究组件')));
    // Close the tour while the catalog is in flight, then allow that response to arrive.
    const draft='保留这段尚未提交的问题';
    await $('home-question').fill(draft);
    let release;
    const gate=new Promise(resolve=>release=resolve);
    const delayCatalog=async route=>{await gate;await route.fallback();};
    await page.route('**/api/literature',delayCatalog);
    const pendingCatalog=page.waitForRequest(r=>r.url().endsWith('/api/literature'));
    await $('home-tour').focus();await page.keyboard.press('Enter');await pendingCatalog;
    await page.keyboard.press('Escape');await $('source-tour').waitFor({state:'hidden'});
    const late=page.waitForResponse(r=>r.url().endsWith('/api/literature'));
    release();await late;await page.unroute('**/api/literature',delayCatalog);
    ok('closing a loading tour keeps the home draft and restores its launch button',await $('home-question').inputValue()===draft && await $('home-tour').evaluate(el=>el===document.activeElement));
    await page.route('**/api/literature/search',r=>r.fulfill({status:503,json:{error:'测试：示例暂时不可用'}}),{times:1});
    await $('home-tour').click();
    const retry=$('tour-body').getByRole('button',{name:'重新加载'});
    await retry.waitFor();
    ok('failed example keeps dialog open with an actionable retry',await $('source-tour').isVisible()&&await $('tour-next').isDisabled());
    const demoRequests=[];
    const recordDemoRequest=r=>{if(r.method()==='POST')demoRequests.push(r.url());};
    page.on('request',recordDemoRequest);
    await $('tour-process').focus();await page.keyboard.press('Enter');
    const demo=$('journey-demo');await demo.waitFor();
    ok('offline process example opens from the lightweight home while the catalog example is unavailable',
      await demo.innerText().then(t=>t.includes('模拟'))&&await demo.locator('[data-demo-phase]').count()===6);
    await demo.locator('[data-demo-phase="3"]').click();
    const claims=demo.locator('.rc-relation-card');await claims.nth(1).click();
    ok('research example uses the interactive evidence scene',await claims.nth(1).getAttribute('aria-pressed')==='true'&&await demo.locator('.em-relation-focus blockquote').innerText().then(t=>!!t.trim()));
    await demo.locator('[data-demo-phase="5"]').click();
    ok('research example connects its sample answer to a saved passage',await demo.locator('.rc-map-passage blockquote').innerText().then(t=>!!t.trim()));
    await page.keyboard.press('Escape');await demo.waitFor({state:'hidden'});
    page.off('request',recordDemoRequest);
    ok('leaving the offline example restores focus and draft without submitting any request',
      demoRequests.length===0&&await $('tour-process').evaluate(el=>el===document.activeElement)&&await $('home-question').inputValue()===draft);
    const searchResponse=page.waitForResponse(r=>r.url().endsWith('/api/literature/search'));
    await retry.click();
    const example=await (await searchResponse).json();
    await page.waitForFunction(()=>!document.querySelector('#tour-next').disabled);
    ok('tour restarts at the real bundled question',await $('tour-body').innerText().then(t=>t.includes(example.question)) && await $('source-tour').getAttribute('data-step')==='0');
    await $('tour-next').focus();await page.keyboard.press('Enter');
    const choices=page.locator('.tour-papers input');
    ok('tour paper choices match local endpoint titles',await choices.count()===example.items.length && await $('tour-body').innerText().then(t=>example.items.every(x=>t.includes(x.title))));
    await page.keyboard.press('ArrowDown');
    const selected=example.items[1];
    await $('tour-next').focus();await page.keyboard.press('Enter');
    const marked=await $('tour-body').locator('mark').innerText();
    const offset=selected.start+[...selected.quote.slice(0,selected.quote.indexOf(marked))].length;
    ok('tour locates a verbatim quote in the keyboard-selected paper with exact offsets',selected.quote.includes(marked) && await $('tour-body').innerText().then(t=>t.includes(selected.title)&&t.includes('第 '+(offset+1)+' 至 '+(offset+[...marked].length)+' 个字符')));
    await $('tour-back').click();
    ok('back preserves selected paper',await choices.nth(1).isChecked());
    await $('tour-next').click();
    await page.waitForFunction(()=>document.querySelector('#source-tour').getAnimations({subtree:true}).every(a=>a.playState!=='running'));
    ok('tour reaches an idle frame without restarting',await $('source-tour').getAttribute('data-step')==='2');
    await shot('tour-desktop');
    let repeatedSearches=0;
    const countSearch=r=>{if(r.url().endsWith('/api/literature/search'))repeatedSearches++;};
    page.on('request',countSearch);
    await $('tour-open').click();
    await page.waitForSelector('#lit-items li',{timeout:15000});
    ok('tour opens the chosen paper in the workbench without another search',repeatedSearches===0&&await page.evaluate(p=>document.activeElement.textContent===p.title&&document.activeElement.closest('li')?.dataset.paperId===p.paper_id,selected));
    page.off('request',countSearch);
    ok('example searches real bundled literature without model',await page.locator('#lit-items li').count()>0&&await $('lit-brief').isDisabled());
    ok('source has inspectable text and public paper link',await page.locator('#lit-items blockquote').first().innerText().then(t=>t.length>=12)&&await page.locator('#lit-items a').count()>0);
    ok('results collapse the search controls and retain paper titles',!await $('lit-query-panel').evaluate(node=>node.open)&&await $('lit-items').innerText().then(t=>t.includes(example.items[0].title)));
    const disclosure=page.locator('#lit-items .quote-disclosure').first();
    await disclosure.click();
    const expandedId=await disclosure.getAttribute('aria-controls');
    ok('long excerpt expands to its full verbatim text',await disclosure.getAttribute('aria-expanded')==='true' && example.items.map(p=>p.quote).includes(await $(expandedId).innerText()));
    await disclosure.click();
    await $('lit-result-title').scrollIntoViewIfNeeded();await shot('sources-desktop');
    for(const [id,suffix] of [['lit-md','.md'],['lit-ris','.ris']]){
      const pending=page.waitForEvent('download');await $(id).click();const file=await pending;
      ok('export '+suffix,file.suggestedFilename().endsWith(suffix)&&fs.readFileSync(await file.path(),'utf8').trim().length>10);
    }
    await editQuery();
    await page.locator('input[name=collection][value=personal]').check();
    await $('lit-question').fill('urban heat shade');
    const source='Street tree shade reduced urban heat in the afternoon across the sampled locations.';
    await $('lit-files').setInputFiles([{name:'Urban heat.txt',mimeType:'text/plain',buffer:Buffer.from(source)}]);
    await $('lit-paste-toggle').click();await $('lit-title').fill('Additional observation');await $('lit-text').fill('Urban heat was recorded in shaded and exposed courtyard locations throughout the afternoon.');
    await $('lit-add').click();await $('lit-search').click();
    await page.waitForSelector('#lit-items li');
    ok('TXT and pasted materials both enter real source search',await page.locator('#lit-papers li').count()===2&&await page.locator('#lit-items li').count()===2);
    ok('short passages fit without extra expansion controls',await page.locator('#lit-items .quote-disclosure').count()===0);
    await editQuery();
    await $('lit-files').setInputFiles([{name:'large.txt',mimeType:'text/plain',buffer:Buffer.alloc(200001,65)}]);
    await page.waitForFunction(()=>document.querySelector('#lit-status').classList.contains('failed'));
    ok('rejected upload preserves existing materials',await page.locator('#lit-papers li').count()===2);
    const doc=await browser.newPage();
    await doc.setContent('<title>Printed materials</title><p style="break-after:page">Background on a different topic.</p><p>Canopy shade lowers summer pavement temperature when solar radiation is highest.</p>');
    const pdf=await doc.pdf();await doc.close();
    await $('lit-pdf-range').locator('summary').click();await $('lit-first-page').fill('2');await $('lit-last-page').fill('2');
    await $('lit-files').setInputFiles([{name:'Pavement.pdf',mimeType:'application/pdf',buffer:pdf}]);
    await page.waitForFunction(()=>document.querySelectorAll('#lit-papers li').length===3);
    await $('lit-question').fill('summer pavement temperature');await $('lit-search').click();
    await page.waitForSelector('#lit-items li');
    ok('PDF search returns actual quote and original physical page',await $('lit-items').innerText().then(t=>t.includes('第 2 页')&&t.includes('pavement temperature')));
    await editQuery();
    await $('lit-question').fill('urban heat shade');
    allowBrief=true;deep=true;await page.evaluate(()=>connect());
    await page.locator('input[name=collection][value=builtin]').check();
    await page.locator('input[name=collection][value=personal]').check();
    await $('lit-question').fill('城市热岛的树荫效应是什么？');
    await $('lit-translate').click();await page.waitForFunction(()=>document.querySelector('#lit-english').value==='urban heat shade');
    await $('lit-english').fill('urban heat shade pavement');
    const request=page.waitForRequest(r=>r.url().endsWith('/api/literature/search'));
    await $('lit-search').click();const payload=(await request).postDataJSON();await page.waitForSelector('#lit-items li');
    ok('English keywords can be edited and searched alongside original question',payload.english_query==='urban heat shade pavement'&&payload.question==='城市热岛的树荫效应是什么？');
    await page.locator('#lit-items .source-location summary').first().click();
    ok('personal result highlights quote in its submitted source text',await page.locator('#lit-items .source-context mark').first().isVisible());
    for(const check of (await page.locator('#lit-items input').all()).slice(1))await check.uncheck();
    await $('lit-brief').click();await page.waitForSelector('#brief-content li');
    const shortQuote=checkedItems[0].quote.split(' ').slice(1,6).join(' ');
    ok('only explicitly selected sources sent to model adapter fixture',checkedItems.length===1&&await $('brief-content').innerText().then(t=>t.includes(shortQuote)));
    const returnTrigger=$('brief-content').getByRole('button',{name:'回看来源 1'});
    await returnTrigger.click();
    ok('synthesis pinpoints just the quoted words and focuses them',await page.locator('mark.desk-cited-text').evaluate(e=>e===document.activeElement)&&await page.locator('mark.desk-cited-text').innerText()===shortQuote);
    await page.getByRole('button',{name:'返回这项发现'}).click();
    ok('source returns to the same finding and restores its original state',await returnTrigger.evaluate(e=>e===document.activeElement)&&await page.locator('mark.desk-cited-text').count()===0);
    await editQuery();
    await page.route('**/api/literature/search',r=>r.fulfill({status:503,json:{error:'Crossref 暂时无法返回论文。'}}));
    await page.locator('input[name=collection][value=crossref]').check();await $('lit-search').click();
    await page.waitForFunction(()=>document.querySelector('#lit-status').textContent.includes('Crossref 暂时'));
    ok('remote service failure leaves local connection intact',await $('connection-state').getAttribute('data-state')==='online');
    await page.unroute('**/api/literature/search');
    await page.locator('.history-open').first().click();
    await $('answer-outline').waitFor();await $('answer-outline').locator('summary').click();
    await $('answer-outline').getByRole('button',{name:'适用范围'}).click();
    ok('report contents navigate to named section',await page.evaluate(()=>document.activeElement.textContent==='适用范围'));
    await page.locator('#answer-text .citation').click();
    ok('inline citation opens source text',await $('evidence-drawer').isVisible()&&await $('evidence-body').innerText().then(t=>t.includes(study.sources[0].text)));
    ok('report citation points to its cited paragraph and recorded paper',await page.locator('.citation-context').innerText().then(t=>t.includes('林冠覆盖率'))&&await page.locator('#evidence-body a').getAttribute('href')==='https://www.semanticscholar.org/paper/'+paper.id);
    await page.keyboard.press('Escape');await $('read-evidence').click();
    ok('evidence review separate from report',await $('answer-main-panel').isHidden()&&await $('answer-evidence-panel').isVisible());
    await shot('evidence');
    await $('graph-tab').click();
    await page.locator('.map-center').waitFor();
    ok('graph opens directly with two related papers and their citation',await page.locator('.map-paper').count()===2&&await page.locator('.map-reason').innerText().then(t=>t.includes('引用')));
    await shot('graph');
    const center=page.getByLabel('选择图中的中心论文');
    const wire=page.locator('.map-link-draw[data-relation=citation]');
    await center.selectOption(paper.id);
    ok('citation arrow points to the cited paper',await wire.getAttribute('marker-end')==='url(#paper-map-citation-tip)'&&!await wire.getAttribute('marker-start'));
    await center.selectOption(neighbor.id);
    ok('reversing the center preserves the direction of citation',await wire.getAttribute('marker-start')==='url(#paper-map-citation-tip)'&&!await wire.getAttribute('marker-end'));
    const originalWire=await wire.elementHandle();
    const originalCurve=await wire.getAttribute('d');
    await page.setViewportSize({width:1240,height:850});
    await page.waitForFunction(old=>document.querySelector('.map-link-draw[data-relation=citation]')?.getAttribute('d')!==old,originalCurve);
    ok('resizing reroutes the existing edge without replaying the layout',await originalWire.evaluate(el=>el.isConnected&&el===document.querySelector('.map-link-draw[data-relation=citation]')));
    await page.setViewportSize({width:1366,height:850});
    await page.locator('.map-reason').click();
    ok('graph explains recorded citation direction',await page.locator('.paper-map-dialog[open]').innerText().then(t=>t.includes(paper.title+' 引用了 '+neighbor.title)));
    await page.keyboard.press('Escape');
    await page.locator('.map-paper[data-paper-id="'+neighbor.id+'"]').click();
    ok('paper map opens original passage and recorded URL',await page.locator('.paper-map-dialog .map-original').innerText().then(t=>t.includes('pavement temperature'))&&await page.locator('.paper-map-dialog a').getAttribute('href')===neighbor.url);
    await page.keyboard.press('Escape');
    await $('journey-tab').click();
    await page.locator('#journey-view .story-route-step').nth(2).click();
    ok('archived research can switch its visible process stage',await page.locator('#journey-view .story-route-step').count()===6&&await page.locator('#journey-view .story-route-step').nth(2).getAttribute('aria-current')==='step');
    await shot('journey');
    await page.locator('.app-navigation [data-screen=library]').click();
    await $('library-search').fill('Street shade');
    await $('library-list').getByText(neighbor.title).first().waitFor();
    ok('paper library filters recorded titles',!(await $('library-list').innerText()).includes(paper.title));
    await shot('library');
    await page.locator('.app-navigation [data-screen=home]').click();
    await $('home-question').fill('城市树木如何影响夏季地表温度？');
    ok('online settings remain outside input',await $('home-more').evaluate(e=>!e.closest('#home-compose'))&&await $('home-start').isEnabled());
    await shot('home-full');
    await $('home-more').click();ok('advanced settings open',await $('research-dialog').isVisible());await shot('dialog');await page.keyboard.press('Escape');
    await page.setViewportSize({width:390,height:844});
    ok('mobile home has no page overflow',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    await page.emulateMedia({reducedMotion:'reduce'});await $('home-tour').click();await $('tour-next').click();await $('tour-next').click();
    ok('mobile reduced-motion tour shows quote and fits within screen',await $('tour-body').locator('mark').isVisible()&&await $('source-tour').evaluate(el=>el.scrollWidth<=el.clientWidth+1&&el.getBoundingClientRect().width<=innerWidth));
    const motion=await $('source-tour').evaluate(el=>el.getAnimations({subtree:true}).filter(a=>a.playState==='running').map(a=>({
      target:a.effect.target.id||a.effect.target.className,property:a.transitionProperty||a.animationName||'WAAPI'
    })));
    assert.deepEqual(motion,[],'reduced-motion tour should have no active transitions');
    ok('reduced-motion tour settles without motion',motion.length===0);
    await shot('tour-mobile');
    await $('tour-close').click();await page.emulateMedia({reducedMotion:'no-preference'});
    await $('home-demo').click();await page.waitForSelector('#lit-items li');await page.evaluate(()=>scrollTo(0,0));
    ok('mobile source desk has no page overflow',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    ok('first actual excerpt appears inside the mobile opening screen',await page.locator('#lit-items blockquote').first().evaluate(e=>e.getBoundingClientRect().top<innerHeight-45));
    ok('mobile result note follows the export controls',await page.evaluate(()=>document.querySelector('.desk-exports').getBoundingClientRect().bottom<=document.querySelector('#lit-note').getBoundingClientRect().top));
    await shot('sources-mobile');
    await $('mobile-menu').click();await page.locator('.app-navigation [data-screen=home]').click();await shot('home-mobile');
    await $('theme-toggle').click();
    ok('dark theme available',await page.locator('html').getAttribute('data-theme')==='dark');
    await page.setViewportSize({width:320,height:720});
    await $('home-tour').click();await $('tour-next').click();
    ok('dark 320px tour keeps all paper labels within the dialog',await $('source-tour').evaluate(el=>el.scrollWidth<=el.clientWidth+1&&el.getBoundingClientRect().right<=innerWidth));
    const buttonColors=await $('tour-next').evaluate(el=>[getComputedStyle(el).color,getComputedStyle(el).backgroundColor]);
    function luminance(color){
      const [r,g,b]=color.match(/[\d.]+/g).slice(0,3).map(x=>Number(x)/255).map(x=>x<=.04045?x/12.92:((x+.055)/1.055)**2.4);
      return r*.2126+g*.7152+b*.0722;
    }
    const lums=buttonColors.map(luminance).sort((a,b)=>a-b);
    ok('dark tour primary action has WCAG AA text contrast',(lums[1]+.05)/(lums[0]+.05)>=4.5);
    await page.keyboard.press('Escape');
    ok('no accidental study submission or browser errors',sent===0&&errors.length===0);
    await page.setViewportSize({width:1366,height:850});
    await page.locator('#sidebar [data-screen=settings]').click();
    await page.waitForFunction(()=>!document.querySelector('#profile-add').disabled);
    ok('settings opens from sidebar footer with four groups',await $('settings-model').isVisible()&&await page.locator('.settings-tabs [role=tab]').count()===4);
    await shot('settings');
    await $('profile-add').click();
    ok('provider dialog opens with a blank credential',await $('model-profile-dialog').isVisible()&&(await $('profile-key').inputValue())==='');
    await page.keyboard.press('Escape');
    await $('settings-tab-model').focus();await page.keyboard.press('ArrowRight');
    ok('settings tab navigation uses arrow keys',await $('settings-search').isVisible()&&await $('settings-tab-search').getAttribute('aria-selected')==='true');
    let submitted, requests=0, cancelled=0, resumed=0;
    const live={...fixture,id:'ef'.repeat(16),status:'running',created_at:new Date().toISOString()};
    await page.route('**/api/runs',r=>{
      if(r.request().method()==='POST'){requests++;submitted=r.request().postDataJSON();live.question=submitted.question;return r.fulfill({json:live});}
      return r.fulfill({json:submitted?[live,fixture]:[fixture]});
    });
    const direction={id:'shade',label:'采样地点',query:'pavement shade measurements'};
    const liveTrace=[
      {seq:1,event:'start',id:'live-plan',kind:'cpu',name:'查询规划',input:{}},
      {seq:2,event:'end',id:'live-plan',status:'success',output:{plan:{dimensions:[direction]}}}
    ];
    await page.route('**/api/runs/'+live.id+'?*',route=>{
      const cursor=Number(new URL(route.request().url()).searchParams.get('after'));
      const events=liveTrace.filter(e=>e.seq>cursor).map(e=>({...e,time:'2026-01-01T10:00:00Z'}));
      return route.fulfill({json:{run:live,events,result:null}});
    });
    await page.route('**/api/runs/'+live.id+'/cancel',r=>{cancelled++;live.status='cancelled';return r.fulfill({json:live});});
    await page.route('**/api/runs/'+live.id+'/resume',r=>{resumed++;live.status='running';return r.fulfill({json:live});});
    await $('new-research').click();
    ok('new research opens the question field',await $('home-question').evaluate(e=>e===document.activeElement));
    await $('home-question').fill('如何比较城市人行道树荫和地表温度？');
    await $('home-range').selectOption('custom');
    await $('custom-value-input').fill('14');await page.locator('#custom-value-form button[type=submit]').click();
    await $('home-start').click();
    await $('progress-strip').waitFor();
    ok('home sends one configured deep study with the custom cap and request ID',requests===1&&submitted?.online_papers===14&&submitted.method==='clinkrag_online'&&/^[a-f0-9-]{36}$/i.test(submitted.client_request_id)&&await $('run-title').innerText()===submitted.question);
    ok('new deep study opens the live process',await $('journey-view').isVisible()&&await $('cancel').isEnabled());
    await page.locator('#story-scene .rc-plan-branch').waitFor();
    await page.evaluate(()=>{
      window.firstLiveBranch=document.querySelector('#story-scene .rc-plan-branch');
      const update=window.researchApp.update;
      window.seenCursors=[];
      window.researchApp.update=state=>{seenCursors.push(state.traceCursor);return update(state);};
    });
    await page.waitForFunction(()=>seenCursors.includes(2));
    ok('empty HTTP poll passes the previous cursor and preserves the live drawing',await page.evaluate(()=>firstLiveBranch===document.querySelector('#story-scene .rc-plan-branch')));
    liveTrace.push(
      {seq:3,event:'start',id:'live-search',kind:'http',name:'论文检索',input:{dimension:direction.id,query:direction.query}},
      {seq:4,event:'end',id:'live-search',status:'success',output:{papers:[{paperId:paper.id,title:paper.title,abstract:paper.text}]}}
    );
    await page.waitForFunction(()=>seenCursors.includes(4) && document.querySelector('[data-direction=shade]')?.getAttribute('aria-pressed')==='true');
    ok('a new HTTP cursor advances the real app to its recorded search result',await page.locator('#story-route [aria-current=step]').innerText().then(t=>t.includes('寻找相关论文')) && await page.locator('#story-scene .rc-full-paper').count()===1);
    await $('cancel').click();await $('run-recovery').waitFor();
    ok('stop preserves the resume control',cancelled===1&&await $('retry-run').innerText()==='继续研究');
    await $('retry-run').click();await $('progress-strip').waitFor();
    ok('resume returns to the same research record',resumed===1&&await $('run-title').innerText()===submitted.question&&await $('journey-view').isVisible());
    study.answer = ['观察方法','主要结果','适用范围'].map((heading,i)=>
      '## '+heading+'\n\n'+Array.from({length:12},(_,j)=>
        (j+1)+'. 这是滚动定位检查的第 '+(i+1)+' 节。树荫与路面温度由不同地点的观察记录进行对比。').join('\n\n')
    ).join('\n\n');
    await page.setViewportSize({width:390,height:844});
    await page.emulateMedia({reducedMotion:'reduce'});
    await $('mobile-menu').click();
    await page.locator('.history-open[data-run-id="'+fixture.id+'"]').click();
    ok('switching from a live cursor to a saved run restores the archived title',await $('run-title').innerText()===fixture.question);
    await $('answer-tab').click();
    await $('read-body').click();
    await $('reading-progress').waitFor();
    await page.waitForFunction(()=>document.querySelector('#reading-progress').getAttribute('aria-valuenow')==='0');
    ok('long report begins with a zero reading position',await $('reading-progress').isVisible());
    await $('answer-outline').locator('summary').click();
    await $('answer-outline').getByRole('button',{name:'主要结果'}).click();
    await page.waitForFunction(()=>document.querySelector('#answer-outline [aria-current="location"]')?.textContent==='主要结果');
    const position=Number(await $('reading-progress').getAttribute('aria-valuenow'));
    ok('chapter jump updates both the outline and reading position',position>0&&position<100);
    await page.evaluate(()=>scrollTo(0,document.documentElement.scrollHeight));
    await page.waitForFunction(()=>document.querySelector('#reading-progress').getAttribute('aria-valuenow')==='100');
    ok('reading position reaches the end in mobile reduced motion',true);
    await $('read-evidence').click();await $('reading-progress').waitFor({state:'hidden'});
    ok('evidence view hides the body reading position',await $('reading-progress').isHidden());
    ok('no exceptions across isolated full-workflow fixtures',errors.length===0);
    ok('all workbench assets and calls stay on the isolated test origin',external.length===0);
    console.log(JSON.stringify({checks,errors,modelReplies:'fixture',exampleAndPersonalSearch:'actual local endpoints'},null,2));
  } finally {if(browser)await browser.close();proc.kill();}
}
main().catch(e=>{console.error(e);process.exitCode=1;});
