/* Read-only walkthrough. All papers, observations and excerpts below are fictional. */
(() => {
  function demoRecords() {
    const question = '夏季增加沿路树荫，会让人更愿意步行吗？';
    const dimensions = [
      {id:'shade', label:'街道树荫与步行意愿', query:'street shade pedestrian willingness summer'},
      {id:'walking', label:'步行意愿与实际出行', query:'walking intention weekly walking frequency'}
    ];
    const papers = [
      {paperId:'design', title:'街区树种与道路养护', year:2023, abstract:'这份模拟资料比较树种的维护需求，记录修剪和养护成本。'},
      {paperId:'park', title:'社区绿道与居民步行意愿', year:2024, abstract:'社区观察记录显示，增加沿路树荫提高了居民夏季午后的步行意愿。'},
      {paperId:'campus', title:'校园步行随访', year:2025, abstract:'校园随访记录显示，步行意愿的提升带动了学生日常步行次数的增加。'},
      {paperId:'maintenance', title:'林荫步道的路面材料', year:2023, abstract:'这份模拟资料考察铺装材料的耐久性，记录路面破损和维修情况。'}
    ];
    const [design, park, campus, maintenance] = papers;
    const labels = {tree:'沿路树荫', intent:'步行意愿', trips:'日常步行次数'};
    const claims = [
      {id:'shade-to-intent', paper_id:park.paperId, source:'tree', target:'intent', type:'reported_causal', target_state:'increases',
        quote:park.abstract, conditions:{population:'社区居民', period:'夏季', method:'unknown'}},
      {id:'intent-to-trips', paper_id:campus.paperId, source:'intent', target:'trips', type:'reported_causal', source_state:'increases', target_state:'increases',
        quote:campus.abstract, conditions:{population:'在校学生', period:'夏季', method:'每周随访'}}
    ];
    const comparison = {
      left:claims[0].id, right:claims[1].id, state:'conflict', matches:['period'], missing:['method'],
      conflicts:[{field:'population', left:'社区居民', right:'在校学生'}]
    };
    const plan = {dimensions, topic_queries:['street shade walking intention']};
    const search = (id, dimension, query, hits, supplemental=false) => ({
      id:'search-'+id, seq:id+1, kind:'http', name:'论文检索', status:'success',
      input:{dimension, query, supplemental}, output:{papers:hits}
    });
    const answer = [
      '社区样本的模拟观察中，沿路树荫增加后，居民表示更愿意在午后步行。[0]',
      '另一份模拟资料记录了学生的步行意愿和步行次数。两份资料涉及不同人群，现有记录不足以估计增加树荫会让社区居民多走多少次。[0][1]'
    ].join('\n\n');
    const sources = [park,campus].map(paper => ({...paper,paper_id:paper.paperId,text:paper.abstract}));
    const records = [
      {id:'plan', seq:1, name:'研究规划', status:'success', output:{plan}},
      search(1,'shade',dimensions[0].query,[design,park]),
      search(2,'walking',dimensions[1].query,[campus,park]),
      search(3,'shade','street canopy walking route summer',[park,maintenance],true),
      {id:'selection', seq:5, name:'选择论文', status:'success', output:{
        selected_papers:[campus,park],
        excluded_papers:[
          {...design,exclusion_reason:'研究的是树种养护，未记录步行意愿。'},
          {...maintenance,exclusion_reason:'关注路面维护，未涉及行人。'}
        ]
      }},
      {id:'extract', seq:6, name:'整理原文关系', status:'success', output:{claims}},
      {id:'check', seq:7, name:'路径、条件核对', status:'success', output:{paths:[],rejected_links:[comparison]}},
      {id:'answer', seq:8, name:'回答生成与完整性检查', status:'success',
        output:{segments:1,characters:answer.length,complete:true,answer,sources}}
    ];
    return {
      run:{question,status:'success'}, records, papers, labels, claims:new Map(claims.map(c=>[c.id,c])),
      result:{research_plan:plan, rejected_links:[comparison], candidate_paths:[], answer, sources},
      info:{status:'done'}, following:false
    };
  }

  const steps = ['拆解问题','查找论文','筛选论文','阅读原句','核对条件','追溯引用'];
  const make = (tag, text, cls) => {
    const element=document.createElement(tag);
    if(text)element.textContent=text;
    if(cls)element.className=cls;
    return element;
  };
  const button = (label, id, cls) => {
    const node=make('button',label,cls);
    node.type='button';
    if(id)node.id=id;
    return node;
  };
  let dialog, openDemo;

  function createDemo() {
    dialog=make('dialog');dialog.id='journey-demo';dialog.setAttribute('aria-labelledby','journey-demo-title');
    const header=make('div',null,'jd-heading');
    const title=make('h2','研究过程示例 · 模拟资料');title.id='journey-demo-title';
    const close=button('关闭','journey-demo-close','secondary');
    header.append(title,close);
    const nav=make('nav',null,'jd-stages');nav.setAttribute('aria-label','示例研究阶段');
    const view=make('div',null,'jd-body'),host=make('div');view.append(host);
    const footer=make('div',null,'jd-footer');
    const back=button('上一步','journey-demo-prev','secondary'),next=button('下一步','journey-demo-next','secondary');
    footer.append(back,next);dialog.append(header,nav,view,footer);document.body.append(dialog);

    const scene=window.createResearchScene(host),record=demoRecords();
    let phase=0,session=0,opener;
    const tabs=steps.map((label,index)=>{
      const tab=button(label);tab.dataset.demoPhase=index;
      tab.addEventListener('click',()=>show(index));nav.append(tab);return tab;
    });
    function show(index){
      const focused=document.activeElement;
      phase=index;
      for(const [i,tab] of tabs.entries()){
        if(i===index)tab.setAttribute('aria-current','step');
        else tab.removeAttribute('aria-current');
      }
      back.disabled=index===0;next.disabled=index===steps.length-1;
      scene.update({...record,phase});
      view.scrollTop=0;
      if((focused===back&&back.disabled)||(focused===next&&next.disabled))tabs[index].focus({preventScroll:true});
    }
    back.onclick=()=>show(phase-1);
    next.onclick=()=>show(phase+1);
    close.onclick=()=>dialog.close();
    dialog.addEventListener('keydown',event=>{
      if(event.key!=='Escape'||!host.querySelector('.rc-inspector:not([hidden])'))return;
      event.preventDefault();event.stopPropagation();host.querySelector('.rc-close').click();
    },true);
    dialog.addEventListener('close',()=>{
      if(dialog.open)return;
      scene.stop();
      if(opener?.isConnected)opener.focus({preventScroll:true});
    });
    openDemo=trigger=>{
      if(dialog.open)return;
      opener=trigger?.focus?trigger:document.activeElement;
      record.run.id='journey-demo-'+(++session);
      dialog.showModal();show(0);tabs[0].focus({preventScroll:true});
    };
  }

  window.openJourneyDemo=function(trigger){
    if(!dialog)createDemo();
    openDemo(trigger);
  };
})();
