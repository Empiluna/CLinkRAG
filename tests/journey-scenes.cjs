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
  await page.setContent('<html lang="zh-CN" data-theme="light"><body><main class="research-story" style="width:100%;max-width:1180px;margin:auto"><div id="scene"></div></main></body></html>');
  await page.addStyleTag({ content: ':root{--paper:#fff;--surface:#f5f6fa;--line:#dfe3ec;--line-soft:#edf0f4;--tint:#efedf9;--ink:#202842;--body:#37435f;--muted:#65718b;--accent:#6b53cb}*{box-sizing:border-box}body{font-family:Segoe UI,Microsoft YaHei,sans-serif;background:#f6f7f9;margin:0;padding:20px}button,select{font:inherit}button,summary{cursor:pointer}button{color:inherit}button:focus-visible{outline:2px solid #6b53cb} [hidden]{display:none!important}' });
  await page.addStyleTag({ path: path.join(root, 'debug_ui/static/journey.css') });
  for (const script of ['marked.umd.js', 'reader.js', 'journey.js']) await page.addScriptTag({ path: path.join(root, 'debug_ui/static', script) });
  await page.evaluate(() => {
    const papers = Array.from({ length: 25 }, (_, i) => ({ paperId: `p${i}`, title: `Research paper ${i + 1}: A complete title about cultural exchange and education across communities`, year: 2020 + i % 6, abstract: `Complete abstract for paper ${i + 1}.` }));
    const dimensions = Array.from({ length: 6 }, (_, i) => ({ id: `d${i}`, label: `研究方向 ${i + 1}：文化传播与受众互动`, query: `cultural exchange direction ${i + 1}` }));
    const records = [{ id: 'plan', seq: 1, status: 'success', output: { plan: { dimensions } } }, ...dimensions.map((d, i) => ({ id: `search${i}`, seq: i + 2, name: '论文检索', kind: 'http', status: 'success', input: { dimension: d.id, query: d.query }, output: { papers: papers.slice(i * 4, i === 5 ? 25 : i * 4 + 4) } })), { id: 'selected', seq: 9, status: 'success', output: { selected_papers: [papers[17], papers[2]], excluded_papers: [papers[1]] } }];
    const claims = new Map(Array.from({ length: 12 }, (_, i) => [`c${i}`, { id: `c${i}`, paper_id: `p${i}`, source: `source${i}`, target: `target${i}`, type: 'associated_with', quote: `The full recorded evidence statement number ${i + 1} remains visible and can be compared with the next statement.`, conditions: { dataset: 'Study participants', setting: 'unknown' } }]));
    window.fixture = { run: { id: 'test-run', question: '文化作品如何在不同地区传播，并形成持续的受众互动？', status: 'success' }, result: { research_plan: { dimensions } }, phase: 0, info: { status: 'done' }, records, claims, papers, labels: {}, following: false };
    window.scene = createResearchScene(document.querySelector('#scene'));
  });
  const phase = async (value, extra = {}) => {
    await page.evaluate(({ value, extra }) => { Object.assign(fixture, extra, { phase: value }); return scene.update(fixture); }, { value, extra });
  };
  await phase(0);
  check('planning shows all six directions with full labels', await page.locator('.rc-plan-branch').count() === 6);
  await page.locator('.rc-query-detail summary').first().click();
  await phase(1, { following: true, searchId: 'search4' });
  check('retrieval follows the actual search direction', await page.locator('[data-direction=d4]').getAttribute('aria-pressed') === 'true');
  await page.locator('[data-direction=d2]').click();
  await page.evaluate(() => scene.finished());
  check('manual direction selection shows its complete papers', await page.locator('.rc-full-paper').count() === 4 && await page.locator('.rc-full-paper').first().getAttribute('data-paper-id') === 'p8');
  await phase(2, { following: false });
  check('selection preserves all candidates, including unassessed papers', await page.locator('.rc-candidate-column .rc-full-paper').count() === 25);
  check('selected papers retain original candidate numbers', await page.locator('.rc-outcome-papers .rc-document-number').allTextContents().then(values => values.join(',') === '18,03'));
  await phase(3);
  check('relationships show every recorded relation', await page.locator('.rc-relation-card').count() === 12);
  await page.evaluate(() => { fixture.result.candidate_paths = [{ checks: Array.from({ length: 8 }, (_, i) => ({ left: `c${i}`, right: `c${i + 1}`, state: ['compatible', 'conflict', 'unknown'][i % 3], matches: ['dataset'], missing: ['setting'], conflicts: [] })) }]; });
  await phase(4);
  check('condition checking is not truncated to three items', await page.locator('.rc-check-item').count() === 8);
  await page.locator('.rc-check-details summary').first().click();
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
  await phase(0);
  check('returning to a scene preserves expanded query details', await page.locator('.rc-query-detail').first().evaluate(node => node.open));
  check('returning to an already displayed scene does not restart animation', await page.evaluate(() => document.querySelector('#scene').getAnimations({ subtree: true }).every(animation => animation.playState !== 'running')));
  const out = path.join(root, 'results/ui-optimization/journey');
  fs.mkdirSync(out, { recursive: true });
  for (const width of [840, 540, 390]) {
    await page.setViewportSize({ width, height: 1100 });
    for (const value of [0, 1, 2, 3, 4, 5]) {
      await phase(value, { following: false });
      check(`phase ${value + 1} fits ${width}px without horizontal overflow`, await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth && [...document.querySelectorAll('.rc-paper-board')].every(node => node.scrollWidth <= node.clientWidth + 1)));
      if (width === 840 || (width === 390 && [0, 5].includes(value))) await page.screenshot({ path: path.join(out, `${width}-phase-${value + 1}.png`), fullPage: true });
    }
  }
  await page.evaluate(() => { fixture.run.id = 'motion-interrupt'; fixture.phase = 0; window.pendingAnimation = scene.update(fixture); });
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
  check('no script errors', errors.length === 0);
  check('no network requests', requests.length === 0);
  fs.writeFileSync(path.join(out, 'validation.json'), JSON.stringify({ checks, errors, requests }, null, 2));
  console.log(JSON.stringify({ passed: checks.length, errors, output: out }, null, 2));
  await browser.close();
})().catch(error => { console.error(error); process.exit(1); });
