"""Compare candidate fusion on a frozen pool using identical, real multilingual BGE logits."""
import argparse
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'longans')]
os.environ.setdefault('HF_HOME',str(ROOT/'.cache/huggingface'))
from benchmark_cs_ai import arxiv_documents, read, QUESTIONS, CACHE, FACETS, aggregate, paired_interval
from clinkrag.runtime import Ranker
from clinkrag.retrieval import fuse_rankings

BASELINE='b0eb8e0b8652e57b7e187e0bfc42f40d25c806af'

def measures(rows,key):
    ranks=[r[key] for r in rows]
    return {'queries':len(rows),'top1':sum(r==1 for r in ranks),
            'top5':sum(r<=5 for r in ranks),'mrr':round(sum(1/r for r in ranks)/len(ranks),4)}

def expert_scores(ranker, previous):
    archive={r['paper_id']:r for r in (json.loads(line) for line in
             (CACHE/'abstracts-csfcube-preds.jsonl').read_text(encoding='utf-8').splitlines())}
    cases=[]
    def dcg(grades):
        return sum((2**g-1)/math.log2(i+2) for i,g in enumerate(grades))
    for facet in FACETS:
        for pid,pool in read(CACHE/f'test-pid2anns-csfcube-{facet}.json').items():
            r=archive[pid]
            sentences=[s for s,kind in zip(r['abstract'],r['pred_labels']) if kind==facet+'_label']
            query=' '.join([r['title'],*(sentences or r['abstract'])])
            plan={'topic_queries':[r['title']],'dimensions':[]}
            judgments=dict(zip(pool['cands'],pool['relevance_adju'],strict=True))
            ps=[dict(paperId=x,title=archive[x]['title'],abstract=' '.join(archive[x]['abstract']))
                for x in sorted(judgments)]
            semantic=ranker.rank(query,ps,text=lambda p:p['title']+'\n'+p['abstract'])
            denominator=dcg(sorted(judgments.values(),reverse=True)[:10])
            case={'qid':pid,'facet':facet,'question_chars':len(' '.join(query.split()))}
            for name,fuse in [('before',previous),('after',fuse_rankings)]:
                top=fuse(query,semantic,plan)[:10]
                grades=[judgments[p['paperId']] for p in top]
                hits=sum(g>=2 for g in grades)
                count=sum(g>=2 for g in judgments.values())
                case[name]={'nDCG@10':round(dcg(grades)/denominator,6),'Hit@3':int(any(g>=2 for g in grades[:3])),
                            'Recall@10':round(hits/count,6) if count else None}
            cases.append(case)
    def metrics(items):
        return {name:aggregate([r[name] for r in items]) for name in ('before','after')}
    return {'protocol':'Same expert-judged CSFCube candidate pools and facet questions as benchmark_cs_ai.py. Both systems receive the same BGE scores and source title as the short search variant. No provider ranking.',
            'metrics':metrics(cases),
            'by_facet':{f:metrics([r for r in cases if r['facet']==f]) for f in FACETS},
            'long_questions':metrics([r for r in cases if r['question_chars']>300]),
            'short_questions':metrics([r for r in cases if r['question_chars']<=300]),
            'interval':paired_interval(*[[dict(qid=r['qid'],**r[name]) for r in cases] for name in ('before','after')],'nDCG@10'),
            'cases':cases}


def evaluate(device,output):
    docs=[dict(paperId=p['paper_id'],title=p['title'],abstract=p['text']) for p in arxiv_documents()]
    qs=[q for q in read(QUESTIONS)['questions'] if q['kind']!='identifier']
    ranker=Ranker(device)
    rows=[]
    with tempfile.TemporaryDirectory() as temp:
        path=Path(temp)/'previous_retrieval.py'
        path.write_bytes(subprocess.check_output(['git','show',BASELINE+':clinkrag/retrieval.py'],cwd=ROOT))
        spec=importlib.util.spec_from_file_location('previous_retrieval',path)
        previous=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(previous)
        for q in qs:
            for language in ('zh','en'):
                query=q[language]
                ranked=ranker.rank(query,docs,text=lambda p:p['title']+'\n'+p['abstract'])
                # The parallel English formulation is provided equally to both fusion
                # versions. Provider hit ordering and model-generated plans are not tested here.
                plan={'topic_queries':[q['en']],'dimensions':[]}
                def rank(fuse):
                    result=fuse(query,ranked,plan)
                    return 1+next(i for i,p in enumerate(result) if p['paperId']==q['target'])
                rows.append({'query_id':q['id'],'language':language,'expected':q['target'],
                             'before':rank(previous.fuse_rankings),'after':rank(fuse_rankings)})
        expert=expert_scores(ranker,previous.fuse_rankings)
    groups={}
    for lang in ('zh','en'):
        part=[r for r in rows if r['language']==lang]
        groups[lang]={key:measures(part,key) for key in ('before','after')}
    report={'fixture':'36 frozen DataCite CS titles/abstracts, one known article per question; no numbered-reference queries. Both systems receive the same real BGE scores and the same parallel English query. No S2 rank is supplied.',
            'baseline':BASELINE,'evaluation':'known-item rank within provided candidate pool, not web recall',
            'summary':groups,'cases':rows,'expert_evaluation':expert}
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps([groups,expert['metrics']],indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device',default='cuda:0')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    evaluate(args.device,args.output)
