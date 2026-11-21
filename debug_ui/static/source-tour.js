/* A user-paced walkthrough of a real search in the bundled open-access collection. */
(() => {
  const dialog = node('dialog');
  dialog.id = 'source-tour';
  dialog.setAttribute('aria-labelledby', 'tour-title');
  dialog.innerHTML = `
    <header class="tour-heading"><h2 id="tour-title">文献查证演示</h2>
      <button type="button" class="icon-button" id="tour-close" aria-label="关闭演示" autofocus></button></header>
    <ol class="tour-route" aria-label="演示步骤"><li>提出问题</li><li>找到论文</li><li>核对原文</li></ol>
    <div class="tour-body" id="tour-body" aria-live="polite" aria-atomic="false"></div>
    <footer class="tour-footer"><button type="button" id="tour-process" class="text-button">查看六步研究示例</button><button type="button" id="tour-back" class="text-button">上一步</button>
      <button type="button" id="tour-next" class="primary">查看论文</button>
      <button type="button" id="tour-open" class="primary" hidden>在工作台打开示例</button></footer>`;
  document.body.append(dialog);
  $('tour-close').append(window.researchIcon('close'));

  const body = $('tour-body');
  let session = 0, step = 0, selected = 0, example;
  const setStep = index => {
    step = index;
    dialog.dataset.step = String(step);
    [...dialog.querySelectorAll('.tour-route li')].forEach((item, i) => {
      if (i === step) item.setAttribute('aria-current', 'step');
      else item.removeAttribute('aria-current');
      item.classList.toggle('visited', i < step);
    });
    $('tour-back').hidden = step === 0;
    $('tour-process').hidden = step !== 0;
    $('tour-next').hidden = step === 2;
    $('tour-next').disabled = !example;
    $('tour-open').hidden = step !== 2;
    $('tour-next').textContent = step === 0 ? '查看找到的论文' : '核对这篇的原句';
  };

  function showStep(index) {
    setStep(index);
    const panel = node('section', undefined, 'tour-panel');
    if (index === 0) {
      panel.append(node('h3', example.question));
      const flow = node('div', undefined, 'tour-search-flow');
      const collection = node('span', '随包文献'), matches = node('span', '找到 ' + example.items.length + ' 篇论文');
      collection.prepend(window.researchIcon('book'));
      matches.prepend(window.researchIcon('paper'));
      const line = node('i'); line.setAttribute('aria-hidden', 'true');
      flow.append(collection, line, matches);
      panel.append(flow);
    } else if (index === 1) {
      panel.append(node('h3', '选择一篇论文'), node('p', '下列论文来自刚才的本地检索。'));
      const list = node('fieldset', undefined, 'tour-papers');
      list.setAttribute('aria-label', '选择要核对的论文');
      example.items.forEach((paper, i) => {
        const label = node('label'), radio = node('input');
        radio.type = 'radio';
        radio.name = 'tour-paper';
        radio.checked = i === selected;
        radio.onchange = () => { selected = i; };
        const text = node('span');
        text.append(node('strong', paper.title), node('small', byline(paper)));
        label.append(radio, text);
        list.append(label);
      });
      panel.append(list);
    } else {
      const paper = example.items[selected];
      const passage = paper.quote;
      // Choose an intact sentence from this example's actual returned passage.
      const sentences = passage.match(/[^.!?。！？]+(?:[.!?。！？]+(?=\s|$)|$)/gu) || [];
      const quote = (sentences.find(s => /radiocarbon (?:dates|dating)/i.test(s))
                     || sentences.find(s => /radiocarbon/i.test(s)) || sentences[0] || passage).trim();
      const at = passage.indexOf(quote);
      const start = paper.start + Array.from(passage.slice(0, at)).length;
      panel.append(node('h3', '这句话出自哪里？'));
      const citation = node('div', undefined, 'tour-citation');
      citation.append(window.researchIcon('paper'), node('strong', paper.title));
      panel.append(citation);
      const block = node('blockquote');
      block.append(node('mark', quote));
      const length = Array.from(quote).length;
      const position = node('div', undefined, 'tour-position');
      position.setAttribute('aria-hidden','true');
      const marker = node('i');
      const span = Array.from(passage).length || 1;
      marker.style.left = (start - paper.start) / span * 100 + '%';
      marker.style.width = length / span * 100 + '%';
      position.append(marker);
      panel.append(block, position, node('small', '收录文本第 ' + (start + 1) + ' 至 ' + (start + length) + ' 个字符'));
      const source = node('div', undefined, 'tour-source');
      source.append(node('span', byline(paper)));
      const url = window.researchReader.paperUrl(paper);
      if (url) {
        const a = node('a', '打开论文');
        a.href = url; a.target = '_blank'; a.rel = 'noopener noreferrer';
        a.append(window.researchIcon('external'));
        source.append(a);
      }
      panel.append(source);
    }
    body.replaceChildren(panel);
  }

  function byline(paper) {
    const authors = paper.authors || [];
    const author = authors.length > 1 ? authors[0] + ' 等' : authors[0];
    return [author, paper.year].filter(Boolean).join(' · ');
  }

  async function start() {
    const ticket = ++session;
    selected = 0;
    example = null;
    setStep(0);
    body.textContent = '正在本机查找示例文献…';
    if (!dialog.open) dialog.showModal();
    try {
      const catalog = await api('/api/literature');
      if (ticket !== session || !dialog.open) return;
      const response = await api('/api/literature/search', {method:'POST', body:JSON.stringify({
        question:catalog.example_question, collection:'builtin', limit:5
      })});
      if (ticket !== session || !dialog.open) return;
      if (!response.items.length) throw new Error('这次检索没有找到原文。');
      example = response;
      showStep(0);
    } catch (error) {
      if (ticket !== session || !dialog.open) return;
      const retry = node('button', '重新加载', 'secondary');
      retry.type = 'button'; retry.onclick = start;
      body.replaceChildren(node('p', error.message), retry);
    }
  }
  $('home-tour').onclick = start;
  $('tour-process').onclick = () => window.openJourneyDemo();
  $('tour-close').onclick = () => dialog.close();
  $('tour-back').onclick = () => {
    showStep(step - 1);
    if ($('tour-back').hidden) $('tour-next').focus();
  };
  $('tour-next').onclick = () => {
    if (!example) return;
    showStep(step + 1);
    if (step === 1) body.querySelector('input:checked').focus();
    else $('tour-open').focus();
  };
  $('tour-open').onclick = () => {
    const result = example, paperId = result.items[selected].paper_id;
    dialog.close();
    window.literatureDesk.openExample(paperId, result);
  };
  dialog.addEventListener('close', () => { if (!dialog.open) { session++; example = null; } });
})();
