/* Synthetic research records only: no network, model calls, or saved-run mutations. */
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs');

(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 1100 } });
  const errors = [], checks = [], requests = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', request => requests.push(request.url()));
  const check = (name, condition) => { assert.ok(condition, name); checks.push(name); };
  const root = path.resolve(__dirname, '..');
  const out = process.env.UI_SCENE_ARTIFACTS || path.join(root, 'results/ui-optimization/journey');
  fs.mkdirSync(out, { recursive: true });
  await page.setContent('<html lang="zh-CN" data-theme="light"><body style="display:block"><section class="research-story" data-presentation="canvas" style="width:min(1180px,100%);margin:auto"><div class="story-layout"><section class="story-main panel"><div id="scene"></div></section></div></section></body></html>');
  const staticRoot = path.join(root, 'debug_ui/static');
  const index = fs.readFileSync(path.join(staticRoot, 'index.html'), 'utf8');
  for (const [, file] of index.matchAll(/<link rel="stylesheet" href="\/([^"?]+)(?:\?[^"]*)?"/g)) {
    await page.addStyleTag({path:path.join(staticRoot, file)});
  }
  for (const script of ['marked.umd.js', 'reader.js', 'journey.js']) await page.addScriptTag({ path: path.join(root, 'debug_ui/static', script) });
  await page.evaluate(() => {
    const papers = Array.from({ length: 25 }, (_, i) => ({ paperId: `p${i}`, title: `Research paper ${i + 1}: A complete title about cultural exchange and education across communities`, year: 2020 + i % 6, abstract: `Complete abstract for paper ${i + 1}.` }));
    const dimensions = Array.from({ length: 6 }, (_, i) => ({ id: `d${i}`, label: `研究方向 ${i + 1}：文化传播与受众互动`, query: `cultural exchange direction ${i + 1}` }));
    const records = [{ id: 'plan', seq: 1, status: 'success', output: { plan: { dimensions } } }, ...dimensions.map((d, i) => ({ id: `search${i}`, seq: i + 2, name: '论文检索', kind: 'http', status: 'success', input: { dimension: d.id, query: d.query }, output: { papers: papers.slice(i * 4, i === 5 ? 25 : i * 4 + 4) } })), { id: 'selected', seq: 9, status: 'success', output: { selected_papers: [papers[17], papers[2]], excluded_papers: [papers[1]] } }];
    const claims = new Map(Array.from({length:12}, (_, i) => [`c${i}`, {
      id:`c${i}`, paper_id:`p${i}`, source:`source${i}`, target:`target${i}`,
      type:i===1 ? 'reported_causal' : 'associated_with',
      quote:`The full recorded evidence statement number ${i + 1} remains visible and can be compared with the next statement.`,
      conditions:{task:'audience response',dataset:i===0?'Museum visitors':'Online viewers',setting:'unknown'}
    }]));
    const labels = {source0:'接触文化作品',target0:'受众参与度',source1:'阅读讨论',target1:'持续参与'};
    window.fixture = { run: { id: 'test-run', question: '文化作品如何在不同地区传播，并形成持续的受众互动？', status: 'success' }, result: { research_plan: { dimensions } }, phase: 0, info: { status: 'done' }, records, claims, papers, labels, following: false };
    window.scene = createResearchScene(document.querySelector('#scene'));
  });
  const phase = async (value, extra = {}) => {
    await page.evaluate(({ value, extra }) => { Object.assign(fixture, extra, { phase: value }); return scene.update(fixture); }, { value, extra });
  };
  await phase(0);
  check('planning shows all six directions with full labels', await page.locator('.rc-plan-branch').count() === 6);
  check('every planned direction has its own visible route', await page.locator('.rc-plan-lines path').evaluateAll(paths => paths.length === 6 && paths.every(path => path.getTotalLength() > 0)));
  await page.locator('.rc-query-detail summary').first().click();
  await phase(1, { following: true, searchId: 'search4' });
  check('retrieval follows the actual search direction', await page.locator('[data-direction=d4]').getAttribute('aria-pressed') === 'true');
  await page.locator('[data-direction=d2]').click();
  await page.evaluate(() => scene.finished());
  check('manual direction selection shows its complete papers', await page.locator('.rc-full-paper').count() === 4 && await page.locator('.rc-full-paper').first().getAttribute('data-paper-id') === 'p8');
  await phase(2, { following: false });
  check('selection preserves all candidates, including unassessed papers', await page.locator('.rc-candidate-column .rc-full-paper').count() === 25);
  check('selected papers retain original candidate numbers', await page.locator('.rc-outcome-papers .rc-document-number').allTextContents().then(values => values.join(',') === '18,03'));
  await page.locator('.rc-locate-paper[data-paper-id=p17]').focus();
  await page.keyboard.press('Enter');
  const locatedPapers = await page.locator('.rc-full-paper[data-located=true]').evaluateAll(nodes =>
    nodes.map(node => [node.dataset.paperId, node.querySelector('.rc-document-number').textContent]));
  check('locating a selected paper highlights its original entry and its matching selection',
    locatedPapers.length === 2 && locatedPapers.every(([id, number]) => id === 'p17' && number === '18'));
  await phase(3);
  check('relationships show every recorded relation', await page.locator('.rc-relation-card').count() === 12);
  await page.locator('.rc-relation-card[data-claim-id=c1]').focus();
  await page.keyboard.press('Enter');
  const relationFocus = page.locator('.em-relation-focus[data-claim-id=c1]');
  const selectedQuote=await relationFocus.locator('blockquote').textContent();
  const endpoints=await relationFocus.locator('.em-factor-track').innerText();
  check('choosing a relation by keyboard shows its actual endpoints and full supporting quote',
    selectedQuote.includes('evidence statement number 2') && endpoints.includes('阅读讨论') && endpoints.includes('持续参与') &&
    await page.locator('.rc-relation-card[data-claim-id=c1]').getAttribute('aria-pressed')==='true');
  await page.evaluate(() => {
    fixture.result.candidate_paths = [{checks: Array.from({length:8}, (_, i) => ({
      left:'c'+i, right:'c'+(i+1), state:i === 0 ? 'conflict' : 'unknown',
      matches:['task'], missing:['setting'],
      conflicts:i === 0 ? [{field:'dataset',left:'Museum visitors',right:'Online viewers'}] : []
    }))}];
  });
  await phase(4);
  check('condition checking is not truncated to three items', await page.locator('.rc-check-item').count() === 8);
  const checkPanel=page.locator('.em-check-focus');
  const conflict=await checkPanel.locator('[data-state=conflict] td').allTextContents();
  const match=await checkPanel.locator('[data-state=match] td').allTextContents();
  check('condition table compares both recorded study populations and distinguishes agreement from missing values',
    conflict.join('|')==='Museum visitors|Online viewers' && match.join('|')==='audience response|audience response' &&
    await checkPanel.locator('[data-state=missing] td').count()===2);
  await page.locator('.rc-check-item').nth(1).click();
  check('choosing another condition check replaces the result and source pair',await checkPanel.getAttribute('data-state')==='unknown' && await checkPanel.locator('.rc-check-details').textContent().then(t=>t.includes('evidence statement number 3')));
  await page.locator('.rc-check-item').first().click();
  await page.locator('.rc-check-details summary').first().click();
  check('opening a condition comparison reveals the two verbatim passages',await checkPanel.locator('blockquote').allTextContents().then(lines=>lines.length===2 && lines[0].includes('statement number 1') && lines[1].includes('statement number 2')));
  await page.screenshot({path:path.join(out,'condition-comparison.png'),fullPage:true});
  await page.evaluate(() => { window.firstCheck = document.querySelector('.rc-check-item'); fixture.records.push({ id: 'unrelated', output: { log: 'unrelated polling update' } }); scene.update(fixture); });
  check('unrelated polling preserves the scene and expanded evidence', await page.evaluate(() => firstCheck === document.querySelector('.rc-check-item') && document.querySelector('.rc-check-details').open));
  await page.evaluate(() => { fixture.result.candidate_paths = []; fixture.result.evidence_scope = { dimensions: fixture.result.research_plan.dimensions.map((d, i) => ({ ...d, paper_ids: fixture.papers.slice(0, i + 1).map(p => p.paperId) })) }; });
  await phase(4);
  check('coverage shows all six directions', await page.locator('.rc-coverage-row').count() === 6);
  await page.evaluate(() => {
    fixture.result.answer = '# 研究结论\n\n' + Array.from({ length: 12 }, (_, i) => `这一段是完整的研究正文 ${i + 1}，描述论文实际发现。[${i}]`).join('\n\n') + '\n\n## 最后的结论\n\n全文结尾仍然完整可见。\n\n## 证据梳理\n\n应单独呈现的证据说明。';
    fixture.result.sources = fixture.papers.slice(0, 12).map(p => ({ ...p, paper_id: p.paperId, text: p.abstract }));
  });
  await phase(5);
  check('generation shows all source fragments, beyond the previous five-item limit', await page.locator('.rc-answer-sources .rc-full-paper').count() === 12);
  check('answer keeps its ending and separates evidence review', await page.locator('.rc-answer-reading').innerText().then(text => text.includes('全文结尾仍然完整可见') && !text.includes('应单独呈现的证据说明')));
  await page.locator('.rc-answer-reading .citation').first().click();
  check('citation opens the exact recorded source', await page.locator('.rc-inspector').isVisible() && await page.locator('.rc-inspector-body').innerText().then(text => text.includes('Complete abstract for paper 1.')));
  await page.keyboard.press('Escape');
  check('closing source inspector restores keyboard focus', await page.locator('.rc-answer-reading .citation').first().evaluate(node => node === document.activeElement));
  await page.evaluate(() => {
    window.originalReport=fixture.result;
    fixture.result={...originalReport,answer:'## 研究结果\n\n第一处研究发现由两份材料说明 [2] [0] [2]。\n\n- 第二处研究发现 [1]。\n\n程序中的 `[4]`，以及超出范围的编号 [99]。',evidence_review:'单独的证据梳理 [3]。'};
    return scene.update(fixture);
  });
  check('the answer map only lists body blocks with valid references',await page.locator('.rc-cited-block option').count()===2 && await page.locator('[data-citation-choice]').evaluateAll(nodes=>nodes.map(n=>n.dataset.citationChoice).join(',')==='2,0'));
  await page.locator('[data-citation-choice="0"]').focus();
  await page.keyboard.press('Enter');
  check('a second source for the same statement opens its unabridged excerpt',await page.locator('.rc-map-passage blockquote').innerText()==='Complete abstract for paper 1.');
  await page.locator('.rc-cited-block').selectOption('1');
  check('switching to a cited list entry replaces both the excerpt and the eligible sources',await page.locator('.rc-map-passage blockquote').innerText()==='Complete abstract for paper 2.' && await page.locator('[data-citation-choice]').count()===1);
  await page.locator('.rc-jump-block').click();
  check('locate in answer focuses the exact original list entry',await page.locator('.rc-answer-reading').evaluate(body=>body.contains(document.activeElement)&&document.activeElement.textContent.includes('第二处研究发现')));
  await page.evaluate(()=>{fixture.result={...originalReport,answer:'正文只有代码 `[1]` 和越界索引 [99]。'};return scene.update(fixture);});
  check('answers without valid in-body citations keep the text and original sources',await page.locator('.rc-citation-map').count()===0 && await page.locator('.rc-answer-sources .rc-full-paper').count()===12 && await page.locator('.rc-answer-reading').innerText().then(t=>t.includes('正文只有代码')));
  check('archives without recorded generation rounds do not show a made-up progress graph',await page.locator('.rc-draft-history').count()===0);
  await page.evaluate(()=>{fixture.result=originalReport;});
  await phase(0);
  check('returning to a scene preserves expanded query details', await page.locator('.rc-query-detail').first().evaluate(node => node.open));
  check('returning to an already displayed scene does not restart animation', await page.evaluate(() => document.querySelector('#scene').getAnimations({ subtree: true }).every(animation => animation.playState !== 'running')));
  await page.evaluate(()=>{
    window.draftState={...fixture,phase:5,run:{...fixture.run,id:'draft',status:'running'},info:{status:'running'},result:{},records:[
      {id:'prepare',name:'CLinkRAG · 有据回答生成',input:{context:{sources:[{title:'实际送入生成的论文',text:'An unabridged source passage for the draft.'}]}}},
      {id:'first-output',name:'CLinkRAG · 回答生成与完整性检查',status:'success',output:{segments:1,characters:49,complete:false}},
      {id:'continuation',name:'CLinkRAG · 回答生成与完整性检查',status:'success',output:{segments:2,characters:147,complete:false}}
    ]};return scene.update(draftState);
  });
  check('unfinished generation shows the saved segment count, character count and continuation state',await page.locator('.rc-draft-board').innerText().then(t=>['1 个片段','2 段','147 个字符','需要续写'].every(s=>t.includes(s))) && await page.locator('.rc-answer-reading').count()===0);
  const rounds=page.locator('.rc-draft-history .rc-round-row');
  const roundText=await rounds.allTextContents();
  const barWidths=await rounds.locator('.rc-round-track i').evaluateAll(bars=>bars.map(bar=>parseFloat(bar.style.width)));
  check('the drafting chart uses recorded cumulative counts for both its labels and bar lengths',
    roundText.length===2 && roundText[0].includes('1 段') && roundText[0].includes('49 个字符') &&
    roundText[1].includes('2 段') && roundText[1].includes('147 个字符') &&
    Math.abs(barWidths[0] - 100/3)<.01 && barWidths[1]===100);
  await page.locator('.rc-draft-inputs summary').click();
  await page.locator('.rc-draft-inputs button').click();
  check('in-progress generation traces its own input packet to the recorded source text',await page.locator('.rc-inspector-body').innerText().then(t=>t.includes('An unabridged source passage for the draft.')));
  await page.keyboard.press('Escape');
  for (const width of [840, 540, 390, 320]) {
    await page.setViewportSize({ width, height: 1100 });
    for (const value of [0, 1, 2, 3, 4, 5]) {
      await phase(value, { following: false });
      check(`phase ${value + 1} fits ${width}px without horizontal overflow`, await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth && [...document.querySelectorAll('.rc-paper-board')].every(node => node.scrollWidth <= node.clientWidth + 1)));
      if (width === 840 || width === 390) await page.screenshot({ path: path.join(out, `${width}-phase-${value + 1}.png`), fullPage: true });
    }
  }
  const bulk = await page.evaluate(() => {
    const papers = Array.from({length:300}, (_, i) => ({paperId:'large-' + i, title:'Paper ' + i, abstract:'Original source for paper ' + i}));
    const direction = {id:'new',label:'文献综述',query:'review'};
    const search = {id:'batch1',seq:1,kind:'http',input:{dimension:'new',query:'review'},status:'success',output:{papers}};
    window.largeScene = {...fixture,run:{...fixture.run,id:'large',status:'running'},phase:1,following:true,searchId:'batch1',records:[search],result:{research_plan:{dimensions:[direction]}}};
    scene.update(largeScene);
    return {count:document.querySelectorAll('.rc-full-paper').length,animations:document.querySelector('#scene').getAnimations({subtree:true}).length};
  });
  check('a batch of 300 papers stays complete with a visible-window animation budget', bulk.count===300 && bulk.animations<=12);
  await page.evaluate(()=>scene.finished());
  await page.locator('[data-paper-id="large-299"]').click();
  check('the last paper in a long list opens its original abstract', await page.locator('.rc-inspector-body').innerText().then(t=>t.includes('Original source for paper 299')));
  await page.keyboard.press('Escape');
  await page.evaluate(()=>{
    const first=largeScene.records[0];
    largeScene.records.push({...first,id:'batch2',seq:2,output:{papers:[first.output.papers[0],{paperId:'additional', title:'A new paper'}]}});
    largeScene.searchId='batch2';largeScene.following=true;return scene.update(largeScene);
  });
  check('the live batch counts only newly returned unique papers', await page.locator('.rc-batch-change').innerText()==='本批新增 1 篇' && await page.locator('.rc-full-paper').count()===301);
  check('batch history explains repeated records in the current query',await page.locator('.rc-batch-note').innerText().then(t=>t.includes('与此前重复 1 篇') && t.includes('review')));
  await page.locator('.rc-batch-picker').selectOption('batch1');
  check('historical batch counts and cumulative total match the selected batch',await page.locator('.rc-batch-change').innerText()==='本批新增 300 篇' && await page.locator('.rc-batch-plot strong').innerText()==='累计 300 篇');
  check('the first batch highlights its 300 distinct papers',await page.locator('.rc-full-paper[data-batch-new=true]').count()===300);
  await page.locator('.rc-batch-picker').selectOption('batch2');
  const additional=page.locator('.rc-full-paper[data-batch-new=true]');
  check('switching batches locates only the new paper and makes it visible in the complete list',
    await additional.count()===1 && await additional.getAttribute('data-paper-id')==='additional' &&
    await additional.evaluate(node=>{
      const list=node.closest('.rc-complete-papers').getBoundingClientRect(), card=node.getBoundingClientRect();
      return card.top<list.bottom && card.bottom>list.top;
    }));
  await page.evaluate(() => { window.scrollTo(0,0);fixture.run.id = 'motion-interrupt'; fixture.phase = 0; window.pendingAnimation = scene.update(fixture); });
  check('new recorded plan has an actual connection drawing animation', await page.evaluate(() => document.querySelector('.rc-branch-link path').getAnimations().some(animation => animation.playState === 'running')));
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.evaluate(() => pendingAnimation);
  check('changing reduced-motion cancels active drawing and releases completion', await page.evaluate(() => document.querySelector('#scene').getAnimations({ subtree: true }).every(animation => animation.playState !== 'running')));
  await page.evaluate(() => { fixture.run.id = 'reduced-motion'; fixture.phase = 0; scene.update(fixture); });
  check('reduced-motion settles immediately with all content present', await page.evaluate(() => document.querySelectorAll('.rc-plan-branch').length === 6 && document.querySelector('#scene').getAnimations({ subtree: true }).every(animation => animation.playState !== 'running')));
  await page.evaluate(() => {
    scene.stop(); document.body.replaceChildren();
    const host = document.createElement('section'); document.body.append(host);
    window.statusNames = { running: '研究中', success: '已完成' };
    window.researchNotice = value => value || '';
    window.journey = createResearchJourney(host);
    window.liveState = { run: { id: 'live-test', method: 'clinkrag_online', question: fixture.run.question, status: 'running' }, result: null, steps: new Map([['plan', { id: 'plan', seq: 1, name: '查询规划', status: 'success', output: { plan: fixture.result.research_plan } }]]) };
    journey.update(liveState);
  });
  await page.waitForFunction(() => document.querySelectorAll('.rc-plan-branch').length === 6);
  check('all six stage navigation items fit a narrow pane', await page.locator('#story-route .story-route-step').evaluateAll(nodes => nodes.length === 6 && nodes.every(node => { const bounds = node.getBoundingClientRect(); return bounds.left >= 0 && bounds.right <= innerWidth; })));
  await page.evaluate(() => {
    for (const id of [1, 2]) liveState.steps.set('live-search' + id, { id: 'live-search' + id, seq: id + 1, name: '论文检索', kind: 'http', status: 'success', input: { dimension: 'd' + id, query: fixture.result.research_plan.dimensions[id].query }, output: { papers: fixture.papers.slice(id * 4, id * 4 + 4) } });
    journey.update(liveState);
  });
  await page.waitForFunction(() => document.querySelector('[data-direction=d2]')?.getAttribute('aria-pressed') === 'true');
  check('live queue advances through real search events and follows the latest direction', await page.locator('#story-route [aria-current=step]').innerText().then(text => text.includes('寻找相关论文')));
  await page.evaluate(() => {
    liveState.result = fixture.result;
    liveState.run.status = 'success';
    liveState.steps.set('answer', { id: 'answer', seq: 5, name: '回答生成', status: 'success', output: { answer: fixture.result.answer, sources: fixture.result.sources } });
    journey.update(liveState);
  });
  await page.waitForFunction(() => !!document.querySelector('.rc-answer-reading'));
  await page.locator('#story-route .story-route-step').first().click();
  check('completed history never offers a misleading live-follow button', await page.locator('#story-follow').isHidden());
  await page.evaluate(()=>journey.update({run:{...liveState.run,id:'archived-result'},steps:new Map(),result:fixture.result}));
  check('an archive without a trace still recognizes its saved plan',await page.locator('#story-route button').first().getAttribute('data-state')==='done');
  await page.locator('#story-route button').first().focus();
  await page.keyboard.press('End');
  check('keyboard navigation selects and focuses the final research stage',await page.locator('#story-route button').last().evaluate(el=>document.activeElement===el && el.getAttribute('aria-current')==='step'));
  await page.emulateMedia({reducedMotion:'no-preference'});
  await page.setViewportSize({width:1200,height:1000});
  const queueStart=await page.evaluate(()=>{
    scrollTo(0,0);
    window.moving={
      run:{...liveState.run,id:'animated-live',status:'running'},result:null,
      steps:new Map([['plan',liveState.steps.get('plan')]])
    };
    journey.update(moving);
    const route=document.querySelector('#story-route');
    const phase=()=>Array.from(route.querySelectorAll('button')).findIndex(b=>b.getAttribute('aria-current')==='step');
    const firstAnimations=document.querySelector('#story-scene').getAnimations({subtree:true}).filter(a=>a.playState==='running');
    window.playbackLog={stages:[phase()],firstFinished:false,retrievalWaited:false};
    Promise.allSettled(firstAnimations.map(a=>a.finished)).then(()=>{playbackLog.firstFinished=true;});
    window.routeObserver=new MutationObserver(()=>{
      const active=phase();
      if(active!==playbackLog.stages.at(-1)){
        playbackLog.stages.push(active);
        if(active===1)playbackLog.retrievalWaited=playbackLog.firstFinished;
      }
    });
    routeObserver.observe(route,{subtree:true,attributes:true,childList:true});
    moving.steps.set('next-search',{...liveState.steps.get('live-search1'),id:'next-search',seq:2});
    moving.steps.set('next-selection',{id:'next-selection',seq:3,name:'摘要筛选与语料构建',status:'success',output:{selected_papers:[fixture.papers[4]]}});
    journey.update(moving);
    return {running:firstAnimations.length,active:phase()};
  });
  check('a burst of later records stays queued behind the active planning drawing',queueStart.running>0 && queueStart.active===0);
  await page.waitForFunction(()=>document.querySelector('#story-route button:nth-child(3)')?.getAttribute('aria-current')==='step');
  check('normal-motion playback visits each stage in order after its actual drawing settles',await page.evaluate(()=>playbackLog.stages.join(',')==='0,1,2' && playbackLog.retrievalWaited));
  await page.evaluate(()=>{
    document.documentElement.dataset.motion='off';document.dispatchEvent(new Event('clink-preferences'));
    moving.run.status='error';moving.steps.set('halted',{id:'halted',seq:4,name:'摘要筛选与语料构建',status:'error',error:'本次运行已中断'});
    journey.update(moving);
  });
  await page.waitForFunction(()=>document.querySelector('#story-route [aria-current=step]')?.dataset.state==='error' && !document.querySelector('#story-status').textContent.includes('等待新结果'));
  check('a terminal update settles with the recorded failure and no stale running indication',await page.locator('#story-follow').isHidden() && await page.locator('.rc-scene-state').getAttribute('data-state')==='error');
  check('disabling interface motion releases every drawing while the recorded result remains accessible',await page.evaluate(()=>document.querySelector('#story-scene').getAnimations({subtree:true}).every(a=>a.playState!=='running') && document.querySelector('.rc-outcome-papers [data-paper-id=p4]')!==null));
  await page.evaluate(()=>{routeObserver.disconnect();delete document.documentElement.dataset.motion;});
  check('no script errors', errors.length === 0);
  check('no network requests', requests.length === 0);
  fs.writeFileSync(path.join(out, 'validation.json'), JSON.stringify({ checks, errors, requests }, null, 2));
  console.log(JSON.stringify({ passed: checks.length, errors, output: out }, null, 2));
  await browser.close();
})().catch(error => { console.error(error); process.exit(1); });
