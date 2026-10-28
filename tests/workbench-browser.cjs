/* Browser acceptance. Existing real answers + explicitly simulated failures/jobs; no paid generation. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'C:/Users/Emp/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..'),out=path.join(root,'results/product-ui-20261019');fs.mkdirSync(out,{recursive:true});
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});const errors=[],checks=[];
 const check=(label,value)=>{assert.ok(value,label);checks.push(label);};
 const p=await browser.newPage({viewport:{width:1366,height:900}});p.on('pageerror',e=>errors.push(e.message));
 await p.goto('http://127.0.0.1:8765/');await p.waitForFunction(()=>document.querySelector('#run-status').textContent==='已完成');await p.locator('.app-navigation [data-screen=research]').click();
 check('completed research opens readable answer',await p.locator('#answer-tab').getAttribute('aria-selected')==='true');
 check('Markdown headings and comparison table render',await p.locator('#answer-text h2').count()>0&&await p.locator('#answer-text table').count()===1);
 check('answer begins above fold',(await p.locator('#answer-text').boundingBox()).y<600);
 check('paths are collapsed after the answer',!await p.locator('#path-section').evaluate(e=>e.open));
 await p.screenshot({path:path.join(out,'reader.png')});
 const citation=p.locator('#answer-text .citation').first();await citation.scrollIntoViewIfNeeded();const before=await p.evaluate(()=>scrollY);await citation.click();
 check('citation opens original evidence',await p.locator('#evidence-drawer').evaluate(e=>e.open)&&!!await p.locator('#evidence-body > .original-text').innerText());
 check('citation does not imply an unrelated highlighted support claim',await p.locator('#evidence-body mark').count()===0);
 await p.screenshot({path:path.join(out,'evidence.png')});await p.keyboard.press('Escape');
 check('closing evidence preserves reading position',Math.abs((await p.evaluate(()=>scrollY))-before)<3);
 check('citation focus restored',await citation.evaluate(e=>e===document.activeElement));
 const security=await p.evaluate(()=>{const box=document.createElement('div');document.body.append(box);researchReader.render(box,'## Safe\n\n<img src=x onerror="window.__unsafe=1">\n\n[bad](javascript:alert(1)) **bold [0]**\n\n```html\n<script>alert(1)</script>\n```',{sources:[{title:'Evidence'}]});const v={unsafe:window.__unsafe,img:box.querySelectorAll('img,script,iframe').length,badLinks:[...box.querySelectorAll('a')].some(a=>a.href.startsWith('javascript:')),citation:box.querySelectorAll('.citation').length};box.remove();return v;});
 check('Markdown blocks HTML execution and unsafe URLs',!security.unsafe&&!security.img&&!security.badLinks&&security.citation===1);
 await p.locator('#new-research').click();await p.locator('#question').fill('用于检验刷新恢复的研究草稿');await p.locator('#method').selectOption('scirag_fixed');await p.locator('#advanced-settings summary').click();await p.locator('#max-tokens').selectOption('3000');await p.locator('#close-composer').click();await p.reload();await p.waitForFunction(()=>document.querySelector('#run-status').textContent==='已完成');await p.locator('.app-navigation [data-screen=research]').click();await p.locator('#new-research').click();
 check('draft and parameters survive refresh',await p.locator('#question').inputValue()==='用于检验刷新恢复的研究草稿'&&await p.locator('#max-tokens').inputValue()==='3000'&&await p.locator('#method').inputValue()==='scirag_fixed');
 await p.screenshot({path:path.join(out,'composer.png')});await p.keyboard.press('Escape');
 const downloadPromise=p.waitForEvent('download');await p.locator('#export-answer').click();const download=await downloadPromise;check('readable Markdown export available',download.suggestedFilename().endsWith('.md'));
 await p.locator('#graph-tab').click();await p.locator('#graph-overview h3').first().waitFor();await p.locator('button[data-explore=local]').click();await p.locator('.paper-node').first().waitFor();
 check('graph keeps readable neighborhoods and full scope count',await p.locator('.paper-node').count()<=10&&(await p.locator('#graph-coverage').innerText()).includes('27'));
 check('graph has readable full-width canvas',(await p.locator('#paper-network').boundingBox()).width>900);
 await p.screenshot({path:path.join(out,'graph.png')});await p.locator('#graph-paper-list').selectOption({index:1});await p.locator('#graph-local-bar button').filter({hasText:'查看中心论文证据'}).click();
 check('paper inspector opens on demand',await p.locator('#graph-inspector').isVisible());await p.locator('#graph-close-inspector').click();check('paper inspector can be dismissed',await p.locator('#graph-inspector').isHidden());
 await p.locator('#graph-fullscreen').click();check('full-screen graph available',await p.locator('body').evaluate(e=>e.classList.contains('graph-fullscreen')));await p.keyboard.press('Escape');check('Escape exits graph full-screen',!await p.locator('body').evaluate(e=>e.classList.contains('graph-fullscreen')));
 await p.locator('#trace-tab').click();check('debug mode preserved with API details opt-in',!await p.locator('#technical').isChecked()&&await p.locator('#steps .step').count()>0);
 await p.locator('#technical').check();await p.locator('#steps .step').last().click();check('raw step inspector remains usable',await p.locator('#detail .payload').count()>0);
 await p.locator('#compare-tab').click();await p.locator('.comparison-table').waitFor();check('comparison remains available',await p.locator('.comparison-table tr').count()===16);
 await p.locator('#answer-tab').click();await p.setViewportSize({width:390,height:844});await p.evaluate(()=>scrollTo(0,0));
 check('mobile answer not buried below input controls',(await p.locator('#answer-text').boundingBox()).y<650);check('mobile has no horizontal overflow',await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 check('mobile navigation does not cover the initial reading view',await p.locator('#sidebar').evaluate(e=>e.getBoundingClientRect().right<=0));await p.screenshot({path:path.join(out,'mobile.png')});
 await p.locator('#mobile-menu').click();await p.locator('#new-research').click();check('mobile composer is accessible',await p.locator('#research-dialog').evaluate(e=>e.open));await p.keyboard.press('Escape');
 // Network failure is simulated in this browser only. No service/job mutation.
 const f=await browser.newPage({viewport:{width:1366,height:900}});f.on('pageerror',e=>errors.push(e.message));await f.route('**/api/config',r=>r.abort());await f.goto('http://127.0.0.1:8765/');await f.waitForFunction(()=>document.querySelector('#connection-state').dataset.state==='offline');await f.locator('#new-research').click();
 check('offline disables paid submission',await f.locator('#submit').isDisabled());check('offline indicator is not green',await f.locator('.dot').evaluate(e=>getComputedStyle(e).backgroundColor)==='rgb(198, 107, 72)');await f.locator('#question').fill('断线后仍保留这个问题');await f.keyboard.press('Escape');await f.unroute('**/api/config');await f.locator('#reconnect').click();await f.waitForFunction(()=>document.querySelector('#connection-state').dataset.state==='online');await f.locator('#new-research').click();check('reconnection preserves typed draft',await f.locator('#question').inputValue()==='断线后仍保留这个问题');await f.keyboard.press('Escape');
 // Explicitly simulated job lifecycle: validates submission + cancellation without an LLM call.
 const sim=await browser.newPage();sim.on('pageerror',e=>errors.push(e.message));const id='f'.repeat(32);let postCount=0,created=false,status='running',request;
 await sim.route('**/api/runs',async r=>{if(r.request().method()==='POST'){postCount++;request=r.request().postDataJSON();created=true;return r.fulfill({json:{...request,id,status,created_at:new Date().toISOString()}});}return r.fulfill({json:created?[{...request,id,status,created_at:new Date().toISOString()}]:[]});});
 await sim.route(`**/api/runs/${id}**`,r=>{if(r.request().method()==='POST')status='cancelled';return r.fulfill({json:r.request().method()==='POST'?{id,status}:{run:{...request,id,status,created_at:new Date().toISOString()},events:[],result:null}});});
 await sim.goto('http://127.0.0.1:8765/');await sim.waitForFunction(()=>document.querySelector('#connection-state').dataset.state==='online');await sim.locator('#home-start').click();await sim.locator('#question').fill('这是浏览器模拟任务，不会发送模型请求');await sim.locator('#submit').click();await sim.locator('#progress-strip').waitFor();check('submit creates one request with stable idempotency key',postCount===1&&/^[a-f0-9-]{36}$/.test(request.client_request_id));await sim.locator('#cancel').click();await sim.locator('#run-recovery').waitFor();check('cancel retains recovery actions',await sim.locator('#recovery-title').innerText()==='已停止');await sim.locator('#retry-run').click();check('retry requires review before any new API call',await sim.locator('#question').inputValue()===request.question&&postCount===1);
 check('no browser script errors',errors.length===0);fs.writeFileSync(path.join(out,'validation.json'),JSON.stringify({checks,errors,paidGenerations:0,simulatedJob:true},null,2));console.log(JSON.stringify({passed:checks.length,errors,output:out}));await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
