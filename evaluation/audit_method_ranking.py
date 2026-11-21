"""Audit top-ten crossings in the production deep candidate ranker with fixed, real BGE data.

Run from a clone with the two historical commits and the previous public benchmark cache:
python evaluation/audit_method_ranking.py --output evaluation/reports/method-ranking-followup.json
"""
import argparse
from functools import lru_cache
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
from statistics import median
from time import perf_counter
from types import ModuleType
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'longans')]
os.environ.setdefault('HF_HOME', str(ROOT/'.cache/huggingface'))
from evaluation.benchmark_cs_ai import CACHE, FACETS, aggregate, paired_interval, read
from evaluation.litsearch_audit import acquire
from clinkrag.online import review_budget
from clinkrag.runtime import Ranker
from clinkrag.retrieval import LexicalIndex, assessment_pool, fuse_rankings, terms
from llms.reranking import options

ORIGINAL = 'b0eb8e0b8652e57b7e187e0bfc42f40d25c806af'
PREVIOUS = '0ec95bd2855784f4e4eb34bd6776a912f7451be6'
CACHE_ROOT = CACHE/'method-audit-v2'


def historic(rev):
    source = subprocess.check_output(['git','show',rev+':clinkrag/retrieval.py'], cwd=ROOT)
    module = ModuleType('historical_retrieval')
    exec(compile(source, rev+'/clinkrag/retrieval.py', 'exec'), module.__dict__)
    return module.fuse_rankings


def csfcube_cases():
    archive = {r['paper_id']:r for r in map(json.loads,(CACHE/'abstracts-csfcube-preds.jsonl').read_text(
        encoding='utf-8').splitlines())}
    for facet in FACETS:
        for pid,pool in read(CACHE/f'test-pid2anns-csfcube-{facet}.json').items():
            r = archive[pid]
            facet_sentences = [s for s,label in zip(r['abstract'],r['pred_labels']) if label==facet+'_label']
            query = ' '.join([r['title'],*(facet_sentences or r['abstract'])])
            grades = dict(zip(pool['cands'],pool['relevance_adju'],strict=True))
            papers = [dict(paperId=i,title=archive[i]['title'],abstract=' '.join(archive[i]['abstract'])) for i in sorted(grades)]
            yield dict(qid=pid,facet=facet,question=query,short_query=r['title'],grades=grades,papers=papers,threshold=2)


def litsearch_cases():
    import pyarrow.parquet as pq
    acquire(CACHE,False)
    data = CACHE/'litsearch'
    questions = {r['_id']:r['text'] for r in pq.read_table(data/'queries.parquet').to_pylist()}
    gold = {}
    for r in pq.read_table(data/'qrels.parquet').to_pylist():
        if r['score']>0:
            gold.setdefault(r['query-id'],set()).add(r['corpus-id'])
    targets = set.union(*gold.values())
    docs = {}
    for batch in pq.ParquetFile(data/'corpus.parquet').iter_batches():
        for d in batch.to_pylist():
            if d['_id'] in targets and d['title'].strip() and d['text'].strip():
                docs[d['_id']] = dict(paperId=d['_id'],title=d['title'],abstract=d['text'])
    eligible = [k for k,rels in gold.items() if rels <= docs.keys()]
    def sample_key(salt,k):
        return hashlib.sha256((salt+k).encode()).digest()
    prior = set(sorted(eligible,key=lambda k:sample_key('CLinkRAG-litsearch-v1:',k))[:100])
    method = re.compile(r'\b(?:methods?|approach(?:es)?|techniques?|algorithms?|architectures?|mechanisms?)\b',re.I)
    fresh = sorted((k for k in eligible if k not in prior and method.search(questions[k])),
                   key=lambda k:sample_key('CLinkRAG-methods-v2:',k))
    ids = sorted(docs)
    index = LexicalIndex([docs[k]['title']+'\n'+docs[k]['abstract'] for k in ids])
    # Two predeclared length strata. Candidate pool = all targets + 64 highest BM25 distractors.
    for long in (True,False):
        for k in [x for x in fresh if (len(' '.join(questions[x].split()))>300)==long][:20]:
            q = questions[k]
            scores = dict(zip(ids,index.scores(q),strict=True))
            neg = sorted((i for i in ids if i not in gold[k]),key=lambda i:-scores[i])[:64]
            pool = sorted(gold[k] | set(neg))
            # Simulate a concise query using only the searcher's words (never a target title).
            short = ' '.join(q.split()[:12])
            yield dict(qid=k,facet='litsearch',question=q,short_query=short,grades={i:int(i in gold[k]) for i in pool},
                       papers=[docs[i] for i in pool],threshold=1)


def fingerprint(case):
    h = hashlib.sha256(case['question'].encode())
    for row in case['papers']:
        for key in ('paperId','title','abstract'):
            h.update(b'\0'+row[key].encode())
    return h.hexdigest()


@lru_cache(maxsize=2)
def inference_settings(device):
    from importlib.metadata import version
    from huggingface_hub import snapshot_download
    import torch
    config = options(device)
    if config['model'] != 'BAAI/bge-reranker-v2-m3':
        raise ValueError('This audit uses BAAI/bge-reranker-v2-m3.')
    snapshot = Path(snapshot_download(config['model'],local_files_only=True)).name
    return {**config,'snapshot':snapshot, 'FlagEmbedding':version('FlagEmbedding'),
            'transformers':version('transformers'),'torch':str(torch.__version__),
            'gpu':torch.cuda.get_device_name(device) if device.startswith('cuda') else ''}


def score_case(ranker, case, device):
    # Cache exact input identities and logits only. Derived rankings can be replayed from one inference run.
    key = case['facet']+'-'+case['qid']
    path = CACHE_ROOT/(key+'.json')
    signature = fingerprint(case)
    if path.exists():
        cached = read(path)
        if cached['input_sha256']==signature and cached.get('settings')==inference_settings(device):
            scores = cached['ordered_scores']
            by_id = {r['paperId']:r for r in case['papers']}
            return [by_id[k]|{'score':v} for k,v in scores]
    ordered = ranker.rank(case['question'],case['papers'],text=lambda p:p['title']+'\n'+p['abstract'])
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(dict(input_sha256=signature,settings=inference_settings(device),
                                   ordered_scores=[[p['paperId'],p['score']] for p in ordered])),
                   encoding='utf-8')
    tmp.replace(path)
    return ordered


def metrics(ranked, grades, threshold):
    gs = [grades[p['paperId']] for p in ranked[:10]]
    def dcg(series):
        return sum((2**g-1)/math.log2(i+2) for i,g in enumerate(series))
    return {'nDCG@10':round(dcg(gs)/dcg(sorted(grades.values(),reverse=True)[:10]),6),
            'Recall@10':round(sum(g>=threshold for g in gs)/sum(g>=threshold for g in grades.values()),6),
            'Hit@3':int(any(g>=threshold for g in gs[:3]))}


def explain_crossings(traces, semantic, full_question, short_query):
    index = LexicalIndex([p['title']+'\n'+p['abstract'] for p in semantic])
    introduced = sorted(set(terms(full_question)) - set(terms(short_query)))
    contributions = [(term,index.scores_for_terms([term])) for term in introduced]
    for trace in traces:
        if (trace['original']['rank'] <= 10) == (trace['previous']['rank'] <= 10):
            continue
        i = trace['semantic_rank']-1
        found = sorted(((term,scores[i]) for term,scores in contributions if scores[i]>0),
                       key=lambda pair:-pair[1])
        trace['added_BM25_terms'] = [{'term':term,'score':round(v,4)} for term,v in found[:6]]


def run(output, device, include_external, original_only):
    variants = {'original':historic(ORIGINAL),'previous':historic(PREVIOUS)}
    if not original_only:
        def every_long_question(query, semantic, plan):
            # Reproduce the earlier experiment which enabled passage matching for all long inputs.
            with patch('clinkrag.retrieval.method_passage_intent',return_value=True):
                return fuse_rankings(query,semantic,plan)
        variants['unrestricted_passages'] = every_long_question
        variants['current'] = fuse_rankings
    ranker = Ranker(device)
    cases = []
    timings = {'previous':[], 'current':[]}
    def collect(case):
        grades = case['grades']
        query = case['question']
        plan = dict(topic_queries=[case['short_query']],dimensions=[])
        semantic = score_case(ranker,case,device)
        results = {k:fn(query,semantic,plan) for k,fn in variants.items()}
        row = dict(qid=case['qid'],facet=case['facet'],chars=len(' '.join(query.split())),
                   pool=len(grades),positive_count=sum(g>=case['threshold'] for g in grades.values()),
                   input_sha256=fingerprint(case))
        for k,ranked in results.items():
            row[k] = metrics(ranked,grades,case['threshold'])
        if 'current' in results:
            row['lexical_scope'] = results['current'][0]['ranking']['lexical_scope']
            old_order = [(p['paperId'],p['fusion_score']) for p in results['previous']]
            new_order = [(p['paperId'],p['fusion_score']) for p in results['current']]
            row['exact_rank_and_score_match_to_previous'] = old_order == new_order
            if row['lexical_scope']=='document' and old_order != new_order:
                raise AssertionError('Protected full-document route differs from previous release')
        if case['facet'] in FACETS and row['chars']>300 and 'current' in variants:
            # Measure CPU fusion in isolation, on identical precomputed real GPU scores.
            for repeat in range(3):
                for label in (timings if (repeat+len(cases))%2==0 else reversed(timings)):
                    start = perf_counter()
                    variants[label](query,semantic,plan)
                    timings[label].append((perf_counter()-start)*1000)
        if case['facet']=='method':
            ranks = {k:{p['paperId']:i for i,p in enumerate(ls,1)} for k,ls in results.items()}
            ids = set.union(*(set(p['paperId'] for p in ls[:10]) for ls in results.values()))
            traces = []
            for old_rank, p in enumerate(semantic,1):
                pid = p['paperId']
                if pid not in ids:
                    continue
                tr = dict(paper_id=pid,title=p['title'],grade=grades[pid],semantic_rank=old_rank)
                for k in results:
                    rk = ranks[k][pid]
                    tr[k] = {'rank':rk,'lexical':results[k][rk-1]['ranking']['lexical_rank']}
                traces.append(tr)
            pool_sizes = {kind:review_budget(dict(plan,question_type=kind),8) for kind in ('focused','comparison')}
            row['review_pool'] = {}
            for k,ranked in results.items():
                row[k]['hits_in_top10'] = sum(grades[p['paperId']]>=2 for p in ranked[:10])
                row['review_pool'][k] = {}
                for kind,budget in pool_sizes.items():
                    sample = assessment_pool(ranked,plan,budget)
                    row['review_pool'][k][kind] = [p['paperId'] for p in sample if grades[p['paperId']]>=2]
            if row['previous']['hits_in_top10'] < row['original']['hits_in_top10']:
                explain_crossings(traces,semantic,query,case['short_query'])
            row.update(title=case['short_query'],top_ten_union=traces)
        return row
    for case in csfcube_cases():
        cases.append(collect(case))
    if include_external:
        for case in litsearch_cases():
            cases.append(collect(case))
    groups = {k:[r for r in cases if r['facet']==k] for k in (*FACETS,'litsearch')}
    groups['all_expert'] = [r for r in cases if r['facet'] in FACETS]
    report = {'commits':{'original':ORIGINAL,'previous':PREVIOUS},'relevance_thresholds':{'CSFCube':2,'LitSearch':1},
              'inference':inference_settings(device),'current_fusion_source_sha256_lf':hashlib.sha256((ROOT/'clinkrag/retrieval.py').read_text(encoding='utf-8').encode()).hexdigest(),
              'external_sampling':'Original LitSearch ML/NLP questions containing a method-family term, excluding the previous 100 questions, deterministic SHA256 by ID. First up to 20 queries on either side of 300 characters. One shared pool per question of its gold articles + 64 BM25 negatives from the 566 annotated articles. Same fixed short variant (first 12 words) and BGE scores across versions. No provider ranks.',
              'source':{'expert':'https://github.com/iesl/CSFCube','external':'https://aclanthology.org/2024.emnlp-main.840/'},
              'summaries':{group:{k:aggregate([r[k] for r in rows]) for k in variants} for group,rows in groups.items() if rows},
              'passage_routed_counts':{group:sum(r.get('lexical_scope')=='best-passage-and-query-variants' for r in rows)
                                       for group,rows in groups.items() if rows},
              'review_pool_protocol':'Production assessment_pool and review_budget for eight requested papers. No provider query provenance or source ranks are available. Reports expert-positive IDs admitted to the focused (16) and comparison (24) review pools. No model assessment or final answer in this controlled component experiment.',
              'long_question_cpu_fusion':{'unit':'ms','protocol':'34 long CSFCube cases, three alternating calls per revision. Only fuse_rankings timed, excluding GPU and HTTP.',
                  'median':{k:round(median(v),3) for k,v in timings.items() if v}},
              'intervals':{},'cases':cases}
    if 'current' in variants:
        for group,rows in groups.items():
            if rows:
                v = [[dict(qid=r['qid'],**r[k]) for r in rows] for k in ('previous','current')]
                report['intervals'][group] = {metric:paired_interval(*v,metric) for metric in ('nDCG@10','Recall@10')}
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report['summaries'],indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device',default='cuda:0')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--external',action='store_true')
    parser.add_argument('--baselines-only',action='store_true')
    args = parser.parse_args()
    run(args.output,args.device,args.external,args.baselines_only)
