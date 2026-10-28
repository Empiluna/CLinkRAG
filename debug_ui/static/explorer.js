/* Bounded paper neighborhoods. Selection uses recorded edges, never invented clusters. */
window.paperExplorer = {
  select(data, {phase='pool',anchor=null,limit=10,page=0,types,min=1}={}) {
    const scope=data.nodes.filter(n=>phase==='pool'||n[phase]),ids=new Set(scope.map(n=>n.id));
    const edges=data.edges.filter(e=>ids.has(e.source)&&ids.has(e.target)&&(!types||types.has(e.type))&&(e.type!=='shared'||e.weight>=min));
    const degree=new Map();for(const e of edges){degree.set(e.source,(degree.get(e.source)||0)+1);degree.set(e.target,(degree.get(e.target)||0)+1);}
    const rank=n=>Number(n.cited)*10000+Number(n.context)*1000+Number(n.seed)*100+(degree.get(n.id)||0);
    const ranked=[...scope].sort((a,b)=>rank(b)-rank(a)||a.title.localeCompare(b.title));
    const center=scope.find(n=>n.id===anchor)||ranked.find(n=>degree.get(n.id)>0)||ranked[0];if(!center)return{scope,ranked,edges,nodes:[],links:[],neighbors:[],pages:0,page:0,degree};
    const connected=new Set(edges.filter(e=>e.source===center.id||e.target===center.id).map(e=>e.source===center.id?e.target:e.source));
    const neighbors=ranked.filter(n=>connected.has(n.id)&&n.id!==center.id),size=Math.max(3,Math.min(11,limit-1));
    const pages=Math.max(1,Math.ceil(neighbors.length/size));page=Math.max(0,Math.min(page,pages-1));
    const nodes=[center,...neighbors.slice(page*size,(page+1)*size)],visible=new Set(nodes.map(n=>n.id));
    // Keep all recorded relation types for this star; no neighbor-to-neighbor hairball.
    const links=edges.filter(e=>visible.has(e.source)&&visible.has(e.target)&&(e.source===center.id||e.target===center.id));
    return{scope,ranked,edges,center,nodes,links,neighbors,pages,page,degree};
  }
};
