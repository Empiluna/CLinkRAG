/* Compare the same offline candidate-list interactions against an optional Git revision. */
const assert = require('node:assert/strict');
const { execFileSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

const root = path.resolve(__dirname, '..');
const revision = process.env.UI_BASE_REV;
if (revision && !/^[a-f0-9]{7,40}$/i.test(revision)) throw new Error('UI_BASE_REV must be a commit hash.');
function staticSource(file) {
  const relative = 'debug_ui/static/' + file;
  return revision
    ? execFileSync('git', ['show', revision + ':' + relative], { cwd: root, encoding: 'utf8' })
    : fs.readFileSync(path.join(root, relative), 'utf8');
}

async function main() {
  const browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL || 'msedge', headless: true });
  const results = [], requests = [], errors = [];
  try {
    const page = await browser.newPage({ viewport: { width: 1366, height: 850 } });
    page.on('request', request => requests.push(request.url()));
    page.on('pageerror', error => errors.push(error.message));
    await page.setContent('<html lang="zh-CN" data-theme="light"><body><section class="research-story" style="width:min(1100px,100%);margin:auto"><div class="story-layout"><section class="story-main panel"><div id="scene"></div></section></div></section></body></html>');
    const sheets = [...staticSource('index.html').matchAll(/<link rel="stylesheet" href="\/([^"?]+)(?:\?[^"]*)?"/g)];
    for (const [, file] of sheets) await page.addStyleTag({ content: staticSource(file) });
    await page.addScriptTag({ content: staticSource('journey.js') });
    await page.evaluate(() => {
      const directions = ['观察方法', '测量时间', '研究人群', '研究地点'].map((label, n) => ({
        label, id: 'd' + n, query: 'urban tree shade aspect ' + n,
      }));
      const papers = Array.from({ length: 240 }, (_, n) => ({
        paperId: 'paper' + n, title: 'Comparing shade and pavement temperatures across sites ' + (n + 1),
        abstract: 'Trees and ground surfaces were observed in this synthetic sample. '.repeat(5),
        year: 2021 + n % 5,
      }));
      window.fixture = {
        run: { id: '', question: '树荫对夏季地表温度的影响有多大？', status: 'success' },
        phase: 1, info: { status: 'done' }, following: false, result: { research_plan: { dimensions: directions } },
        records: directions.map((d, n) => ({
          id: 'request' + n, seq: n + 1, kind: 'http', status: 'success', input: { dimension: d.id, query: d.query },
          output: { papers: papers.slice(n * 60, (n + 1) * 60) },
        })),
        claims: new Map(), papers, labels: {},
      };
      window.scene = createResearchScene(document.querySelector('#scene'));
      window.afterFrames = () => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    });
    for (let n = 0; n < 3; n++) {
      const sample = await page.evaluate(async iteration => {
        const host = document.querySelector('#scene');
        const visibleAnimations = () => host.getAnimations({ subtree: true }).filter(a => ['running','pending'].includes(a.playState)).length;
        const longTasks = [];
        const observer = new PerformanceObserver(entries => longTasks.push(...entries.getEntries().map(e => e.duration)));
        observer.observe({ type: 'longtask' });
        await afterFrames();
        const start = performance.now();
        fixture.run.id = 'record'+iteration;
        scene.update(fixture);
        const buildMs = performance.now() - start;
        const initialAnimations = visibleAnimations();
        const cards = host.querySelectorAll('.rc-full-paper').length;
        await afterFrames();
        const entryFramesMs = performance.now() - start;
        const list=host.querySelector('.rc-complete-papers');
        const bounds=list.getBoundingClientRect();
        const visibleCards=[...list.children].filter(row=>{
          const rect=row.getBoundingClientRect();
          return rect.bottom>Math.max(0,bounds.top) && rect.top<Math.min(innerHeight,bounds.bottom);
        }).length;
        await scene.finished();
        const button = host.querySelector('[data-direction=d2]');
        await afterFrames();
        const clickStart = performance.now();
        button.click();
        const dispatchMs = performance.now() - clickStart;
        await afterFrames();
        const directionFramesMs = performance.now() - clickStart;
        await scene.finished();
        await afterFrames();
        longTasks.push(...observer.takeRecords().map(e => e.duration));
        observer.disconnect();
        return { cards, visibleCards, listTop:bounds.top, listHeight:bounds.height, directionCards: host.querySelectorAll('.rc-full-paper').length,
          initialAnimations, idleAnimations: visibleAnimations(), buildMs, dispatchMs, entryFramesMs, directionFramesMs, longTasks };
      }, n);
      assert.equal(sample.cards, 240);
      if (!n && process.env.UI_PERF_SCREENSHOT) await page.screenshot({path:process.env.UI_PERF_SCREENSHOT});
      assert.ok(sample.visibleCards > 0 && sample.visibleCards < 240, 'A scrollable list of source cards is visible: '+JSON.stringify(sample));
      assert.equal(sample.directionCards, 60);
      assert.equal(sample.idleAnimations, 0);
      if (!revision) assert.ok(sample.initialAnimations <= 16, 'Bound item motion to what readers can see');
      results.push(sample);
    }
    await page.emulateMedia({ reducedMotion: 'reduce' });
    const reduced = await page.evaluate(async () => {
      fixture.run.id = 'reduced-motion'; await scene.update(fixture);
      return { cards: document.querySelectorAll('.rc-full-paper').length,
        active: document.querySelector('#scene').getAnimations({ subtree: true }).filter(a => a.playState === 'running').length };
    });
    assert.deepEqual(reduced, { cards: 240, active: 0 });
    assert.deepEqual(requests, []); assert.deepEqual(errors, []);
    const report = { revision: revision || 'working tree', browser: browser.version(), viewport: [1366,850],
      fixture: '240 synthetic papers; 4 directions of 60, switch to direction 3', runs: results, reduced, requests, errors };
    const json = JSON.stringify(report, (_, value) => typeof value === 'number' ? Math.round(value * 10) / 10 : value, 2);
    if (process.env.UI_METRICS) fs.writeFileSync(process.env.UI_METRICS, json + '\n');
    console.log(json);
  } finally { await browser.close(); }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
