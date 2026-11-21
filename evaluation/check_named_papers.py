"""Check six fixed named CS works against ordinary S2 hits and the production ID lookup."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT), str(ROOT/'longans')]
from clinkrag.online import lookup_references
from clinkrag.paper_ids import matches_reference, paper_references
from llms.settings import load_settings
from s2_transport import request


CASES = [
    ('arXiv:1706.03762', 'transformer neural machine translation attention'),
    ('doi:10.18653/v1/N19-1423', 'bidirectional transformer pretraining language understanding'),
    ('arXiv:2106.09685', 'low rank adaptation large language models'),
    ('arXiv:2205.14135', 'io aware exact attention GPU memory'),
    ('doi:10.1145/1327452.1327492', 'distributed map reduce data processing clusters'),
    ('arXiv:2309.06180', 'paged attention memory management language model serving'),
]


def benchmark():
    key=load_settings().get('S2_API_KEY')
    if not key:
        raise RuntimeError('需要设置 S2_API_KEY 才能复测同一检索服务。')
    refs=[paper_references(label)[0] for label,_ in CASES]
    exact=lookup_references(refs,key,max_attempts=2)
    rows=[]
    for (_,query),ref in zip(CASES,refs):
        result=request('GET','https://api.semanticscholar.org/graph/v1/paper/search',
                       params={'query':query,'limit':5,'fields':'title,externalIds'},
                       headers={'x-api-key':key},timeout=(8,25),max_attempts=3)
        hits=result.json()['data'] if result.ok else []
        pos=next((i for i,p in enumerate(hits,1) if matches_reference(ref,p)),None)
        paper=exact[ref]
        rows.append({'reference':ref,'topic_query':query,'topic_http_status':result.status_code,'topic_rank_at_5':pos,
                     'resolved_paper':paper['paperId'] if paper else None,
                     'title':paper.get('title') if paper else None,
                     'has_usable_abstract':bool(paper and len(paper.get('abstract') or '')>=40)})
    return {'checked_at':datetime.now(timezone.utc).isoformat(),
            'method':'Live read-only Semantic Scholar Graph API. Six prepared topical queries, top 5 each; one additional batch for the six IDs through the production resolver. Known-item identity only, no general relevance labels or answer generation.',
            'topic_queries_evaluated':sum(r['topic_http_status']==200 for r in rows),
            'topic_hits_at_5':sum(r['topic_rank_at_5'] is not None for r in rows),
            'verified_batch_hits':sum(bool(r['resolved_paper']) for r in rows),
            'combined_hits':sum(bool(r['resolved_paper']) or r['topic_rank_at_5'] is not None for r in rows),
            'logical_requests_before_transport_retries':7,'cases':rows}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    report=json.dumps(benchmark(),indent=2,ensure_ascii=False)
    if args.output:args.output.write_text(report+'\n',encoding='utf-8')
    print(report)
