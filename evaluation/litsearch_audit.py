"""Held-out LitSearch slice. Only metadata, compiler-independent hashes and query IDs are published."""
import hashlib
from urllib.request import urlopen

REVISION = 'f9c8810dcec439c17a4a6ed18baec1922a49b0c4'
FILES = {
    'corpus':'86fd423e7e80ab5b18549452e1eb5d6b421a791d97e2411e039878bb5da5cc3a',
    'queries':'2d89d6829b15d815026d62e2cd5c4cb670fffed9d2d6d4a077c8ca7b8c5936c5',
    'qrels':'1743433432694d1450b9df2c4514d77cb6dc960501dc8be6d1ce5d273baf4430',
}
COUNT = 100


def acquire(cache, download):
    path = cache / 'litsearch'
    path.mkdir(parents=True, exist_ok=True)
    for name, digest in FILES.items():
        dest = path / (name+'.parquet')
        if not dest.exists() and download:
            url = f'https://huggingface.co/datasets/mteb/LitSearchRetrieval/resolve/{REVISION}/{name}/test-00000-of-00001.parquet?download=true'
            with urlopen(url, timeout=120) as response:
                body = response.read(36_000_001)
            if hashlib.sha256(body).hexdigest() != digest:
                raise ValueError(f'Wrong LitSearch snapshot: {name}')
            dest.write_bytes(body)
        if not dest.exists() or hashlib.sha256(dest.read_bytes()).hexdigest() != digest:
            raise ValueError(f'Missing or modified {dest}: use --download with a clean cache.')


def evaluate(cache, search, run_query):
    import pyarrow.parquet as pq
    base = cache / 'litsearch'
    query_text = {r['_id']:r['text'] for r in pq.read_table(base/'queries.parquet').to_pylist()}
    relevant = {}
    for judgment in pq.read_table(base/'qrels.parquet').to_pylist():
        if judgment['score'] > 0:
            relevant.setdefault(judgment['query-id'],set()).add(judgment['corpus-id'])
    target_ids = set.union(*relevant.values())
    docs = {}
    for batch in pq.ParquetFile(base/'corpus.parquet').iter_batches():
        for row in batch.to_pylist():
            id_ = row['_id']
            if id_ in target_ids and (row['text'] or '').strip() and (row['title'] or '').strip():
                docs[id_] = {'paper_id':id_, 'text':row['text'], 'title':row['title']}
    papers = [docs[key] for key in sorted(docs)]
    eligible = [id_ for id_,rels in relevant.items() if rels <= docs.keys()]
    sample = sorted(eligible, key=lambda id_:hashlib.sha256(('CLinkRAG-litsearch-v1:'+id_).encode()).digest())[:COUNT]
    result = []
    for qid in sample:
        ranked = run_query(search, query_text[qid], papers, 10)
        rels = relevant[qid]
        hits = [i for i,id_ in enumerate(ranked,1) if id_ in rels]
        result.append({'qid':qid, 'rank10':min(hits, default=None), 'expected':sorted(rels),
                       'top':ranked[:3], 'Recall@10':round(len(hits)/len(rels),6)})
    return {'corpus':len(papers), 'missing_metadata':len(target_ids - docs.keys()), 'eligible_queries':len(eligible),
            'all_queries':len(query_text), 'cases':result}


def report(results, aggregate, paired_interval):
    for name,item in results.items():
        rows = item['cases']
        item['summary'] = aggregate(rows, True) | {'Recall@10':round(sum(r['Recall@10'] for r in rows)/len(rows),4)}
    old,new = results['previous']['cases'],results['current']['cases']
    return {
        'official_source':'https://aclanthology.org/2024.emnlp-main.840/',
        'query_provenance':'The official LitSearch collection combines author-written questions and '
        'expert-reviewed questions constructed using citation contexts. The hash sample mixes origins.',
        'snapshot':'https://huggingface.co/datasets/mteb/LitSearchRetrieval/tree/'+REVISION,
        'protocol':'Fixed diagnostic subset, not official full-corpus scores. Common pool includes every gold '
        'paper in the original 597 questions with both title and abstract. Every other paper is a competitor. '
        'Use the 100 lowest SHA256 based on CLinkRAG-litsearch-v1: + query ID among queries with all targets present.',
        'metadata_files_sha256':FILES,'common_pool_papers':results['current']['corpus'],
        'positive_papers_without_searchable_metadata':results['current']['missing_metadata'],
        'eligible_queries':results['current']['eligible_queries'], 'sampled_queries':len(new),
        'scores':{name:item['summary'] for name,item in results.items()},
        'interval':paired_interval(old,new,'Hit@1'),
        'queries':[{'qid':a['qid'], 'targets':a['expected'], 'baseline_rank10':a['rank10'],
                    'current_rank10':b['rank10'], 'baseline_recall10':a['Recall@10'],
                    'current_recall10':b['Recall@10']} for a,b in zip(old,new,strict=True)]
    }
