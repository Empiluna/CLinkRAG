/* Small, finite transitions. All artwork below is decorative; the evidence graph is separate. */
(() => {
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  const paths = {
    plus:'M12 5v14M5 12h14',
    book:'M12 6c-3-2-7-2-9-1v14c3-1 6-1 9 1 3-2 6-2 9-1V5c-2-1-6-1-9 1Zm0 0v14',
    graph:'M8 6l8 2M6 9l3 8m8-6-5 6M8 5a2 2 0 1 1-4 0 2 2 0 0 1 4 0Zm12 4a2 2 0 1 1-4 0 2 2 0 0 1 4 0ZM12 19a2 2 0 1 1-4 0 2 2 0 0 1 4 0Z',
    trace:'M7 5h14M7 12h14M7 19h14M3 5h.01M3 12h.01M3 19h.01',
    compare:'M4 20V10h5v10m6 0V4h5v16M2 20h20',
    copy:'M9 9h11v12H9ZM5 16H3V3h12v2',
    download:'M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5',
    refresh:'M20 8a8 8 0 1 0 0 8M20 3v5h-5',
    close:'m6 6 12 12M6 18 18 6',
    menu:'M4 6h16M4 12h16M4 18h16',
    sun:'M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0ZM12 2v2m0 16v2M2 12h2m16 0h2M5 5l1 1m12 12 1 1M5 19l1-1M18 6l1-1',
    moon:'M20.5 13A8.5 8.5 0 0 1 11 3.5 8.5 8.5 0 1 0 20.5 13Z',
    link:'m9 15 6-6M10 7l3-3a5 5 0 0 1 7 7l-3 3M14 17l-3 3a5 5 0 0 1-7-7l3-3',
  };
  function icon(name) {
    const s=document.createElementNS('http://www.w3.org/2000/svg','svg');
    s.setAttribute('viewBox','0 0 24 24');s.setAttribute('aria-hidden','true');s.classList.add('ui-icon');
    const p=document.createElementNS(s.namespaceURI,'path');p.setAttribute('d',paths[name]);s.append(p);return s;
  }
  for(const [id,name] of Object.entries({'new-research':'plus','answer-tab':'book','graph-tab':'graph','trace-tab':'trace','compare-tab':'compare','copy-answer':'copy','export-answer':'download','download':'download','rerun':'refresh','close-composer':'close','close-evidence':'close','mobile-menu':'menu','graph-close-inspector':'close'})){
    const b=document.getElementById(id);if(!b)continue;
    if(['close-composer','close-evidence','mobile-menu','graph-close-inspector'].includes(id))b.replaceChildren();
    if(id==='new-research')b.textContent='新建研究';
    b.prepend(icon(name));b.classList.add('with-icon');
  }
  document.querySelector('.brand-icon').replaceChildren(icon('link'));
  const emblem=document.createElement('div');emblem.className='research-emblem';emblem.setAttribute('aria-hidden','true');
  emblem.innerHTML='<svg viewBox="0 0 240 200"><ellipse cx="120" cy="100" rx="92" ry="45" transform="rotate(-35 120 100)"/><ellipse cx="120" cy="100" rx="92" ry="45" transform="rotate(35 120 100)"/><ellipse cx="120" cy="100" rx="92" ry="45" transform="rotate(90 120 100)"/><circle cx="120" cy="100" r="19"/><circle cx="120" cy="100" r="4" fill="currentColor"/><circle cx="52" cy="53" r="4" fill="currentColor"/><circle cx="181" cy="45" r="3" fill="currentColor"/><circle cx="120" cy="192" r="3" fill="currentColor"/></svg>';
  document.querySelector('.run-banner').append(emblem);document.getElementById('welcome').append(emblem.cloneNode(true));
  const toggle=document.getElementById('theme-toggle');
  function themeLabel(){const dark=document.documentElement.dataset.theme==='dark';toggle.replaceChildren(icon(dark?'sun':'moon'));toggle.setAttribute('aria-label',dark?'切换浅色模式':'切换深色模式');toggle.title=toggle.getAttribute('aria-label');}
  toggle.onclick=()=>{document.documentElement.dataset.theme=document.documentElement.dataset.theme==='dark'?'light':'dark';try{localStorage.setItem('clinkrag-theme',document.documentElement.dataset.theme);}catch{}themeLabel();};themeLabel();

  const list=document.querySelector('[role=tablist]'),indicator=document.createElement('span');
  indicator.className='tab-indicator';indicator.setAttribute('aria-hidden','true');list.prepend(indicator);
  const positionIndicator=()=>{const t=list.querySelector('[aria-selected=true]');if(!t||!t.offsetWidth)return;indicator.style.width=t.offsetWidth+'px';indicator.style.transform=`translateX(${t.offsetLeft}px)`;list.parentElement.classList.add('motion-ready');};
  new MutationObserver(positionIndicator).observe(list,{subtree:true,attributes:true,attributeFilter:['aria-selected']});
  new ResizeObserver(positionIndicator).observe(list);positionIndicator();

  const ongoing=new Set();
  function enter(target){
    if((reduced.matches||document.documentElement.dataset.motion==='off')||document.hidden||target.hidden)return;
    const old=target.getAnimations();old.forEach(a=>a.cancel());
    const a=target.animate([{opacity:0},{opacity:1}],{duration:180,easing:'ease-out'});
    ongoing.add(a);a.finished.catch(()=>{}).finally(()=>ongoing.delete(a));
  }
  for(const id of ['answer-view','trace-view','compare-view','graph-view','welcome','research-content','toast']){
    const target=document.getElementById(id);let hidden=target.hidden;
    new MutationObserver(()=>{if(hidden&&!target.hidden)enter(target);hidden=target.hidden;}).observe(target,{attributes:true,attributeFilter:['hidden']});
  }
  reduced.addEventListener('change',()=>{if(reduced.matches)for(const a of ongoing)a.cancel();});
  document.addEventListener('clink-preferences',()=>{if(document.documentElement.dataset.motion==='off')for(const a of ongoing)a.cancel();});
  document.addEventListener('visibilitychange',()=>{if(document.hidden)for(const a of ongoing)a.finish();});
  const banner=document.querySelector('.run-banner');let shineFrame=0;
  banner.addEventListener('pointermove',e=>{
    if((reduced.matches||document.documentElement.dataset.motion==='off')||e.pointerType!=='mouse')return;
    cancelAnimationFrame(shineFrame);shineFrame=requestAnimationFrame(()=>{const r=banner.getBoundingClientRect();banner.style.setProperty('--shine-x',`${e.clientX-r.left}px`);banner.style.setProperty('--shine-y',`${e.clientY-r.top}px`);});
  });
})();
