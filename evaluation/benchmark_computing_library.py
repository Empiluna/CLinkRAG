"""Measure the production proceedings lookup and verify equivalent prepared/dynamic results."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from statistics import median
from time import perf_counter
from unittest.mock import patch

from clinkrag import computing
from debug_ui import literature

QUERIES = ['图神经网络', '分布式共识', '数据库查询优化', '类型系统', '动态规划', '大语言模型',
           'graph neural network', 'distributed consensus', 'query optimization', 'type systems',
           'dynamic programming', 'large language models']


def timed(call):
    start = perf_counter()
    value = call()
    return round(1000*(perf_counter()-start),3), value


def verify_result(result, docs):
    for item in result['items']:
        source = docs[item['paper_id']]
        assert item['quote'] and item['quote'] == source['text'][item['start']:item['end']]
        assert item['authors'] == source['authors'] and item['license'] == source['license']
        assert item['url'] in result['markdown'] and item['container'] in result['ris']
    return [(x['paper_id'],x['score'],x['start'],x['end']) for x in result['items']]


def benchmark():
    corpus = computing.DATA.read_text(encoding='utf-8')
    docs = {row['paper_id']:row for row in map(json.loads,corpus.splitlines())}
    assert all(p['authors'] and p['license'] and p['url'] for p in docs.values())
    venues = Counter(p['container'] for p in docs.values())
    kinds = ('prepared', 'rebuild')
    samples = {k:{'first_query_ms':[], 'warm_12_queries_ms':[]} for k in kinds}
    snapshot = computing.FEATURES
    import gzip
    with gzip.open(snapshot,'rt',encoding='utf-8') as f:
        assert json.load(f)['signature'] == computing.feature_signature(corpus)
    rankings = {}
    for repeat in range(5):
        for kind in (kinds if repeat%2==0 else kinds[::-1]):
            computing._collection.cache_clear()
            with patch.object(computing,'FEATURES',snapshot if kind=='prepared' else snapshot.with_suffix('.absent')):
                def search(q):
                    return literature.literature_search({'question':q,'collection':'computing','limit':5})
                initial,_ = timed(lambda:search(QUERIES[0]))
                first_pass = {q:verify_result(search(q),docs) for q in QUERIES}
                if rankings:
                    assert rankings==first_pass
                rankings=first_pass
                elapsed,_ = timed(lambda:[search(q) for q in QUERIES])
                samples[kind]['first_query_ms'].append(initial)
                samples[kind]['warm_12_queries_ms'].append(elapsed)
    assert all(rankings.values())
    for group in samples.values():
        group.update({key+'_median':median(values) for key,values in list(group.items())})
    # Deterministic title lookup for every included venue, with the exact source
    # slice and both export formats checked at the workbench service boundary.
    title_checks=[]
    for venue in sorted(venues):
        papers=sorted((p for p in docs.values() if p['container']==venue), key=lambda p:p['paper_id'])
        target=papers[len(papers)//2]
        result=literature.literature_search({'collection':'computing','question':target['title'],'limit':5})
        ranked=verify_result(result,docs)
        assert ranked[0][0]==target['paper_id'], target['title']
        title_checks.append({'venue':venue,'id':target['paper_id'],'title':target['title'],'rank':1})
    return {'documents':len(docs),'venues':dict(sorted(venues.items())),
            'source_sha256_lf':hashlib.sha256(corpus.encode()).hexdigest(),
            'protocol':'Five alternating runs in one process. First query rebuilds or loads the index; the OS file cache may be warm. Each warm lap issues the same 12 service calls, top 5, including excerpt and export creation. This is application time, not network time.',
            'timing':samples,'queries':{q:{'hits':len(h),'first_id':h[0][0]} for q,h in rankings.items()},
            'prepared_dynamic_all_ids_scores_and_offsets_equal':True,'known_title_checks':title_checks}


def online():
    query='graph neural networks oversmoothing'
    rows=[]
    with patch.object(literature.requests,'get',wraps=literature.requests.get) as request:
        for _ in range(2):
            before=request.call_count
            elapsed,result=timed(lambda:literature.literature_search({'question':query,'collection':'crossref','limit':3}))
            rows.append({'ms':elapsed,'http_calls':request.call_count-before,'dois':[x['doi'] for x in result['items']]})
    assert rows[0]['http_calls']==1 and rows[1]['http_calls']==0 and rows[0]['dois']==rows[1]['dois'] and rows[0]['dois']
    return {'query':query,'runs':rows}


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--crossref',action='store_true')
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    result=benchmark()
    if args.crossref:
        result['crossref']=online()
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result['timing']))
