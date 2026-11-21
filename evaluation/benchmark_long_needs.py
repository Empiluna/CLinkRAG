"""Held-out deep ranking on all 60 BIRCO DORIS-MAE test queries using real BGE scores."""
import argparse
from collections import defaultdict
import hashlib
import json
from math import log2
from pathlib import Path
from statistics import mean
from unittest.mock import patch
from urllib.request import urlopen

from audit_method_ranking import CACHE, PREVIOUS, ROOT, Ranker, fuse_rankings, historic, score_case
from benchmark_cs_ai import paired_interval
from clinkrag import retrieval

REVISION = '71bd4abb260b3c0e38c51354179e41c16192522a'
SOURCE = 'https://huggingface.co/datasets/mteb/BIRCO-DorisMae-Test'
DIGESTS = {'corpus':'d6ac4461a42b43c7237e70caf428af0b874a78c02364db82bd27a970b626c04b',
           'default':'e3b04f51a097f74d1aa3dffa70eb9643d25a2ee2c104116a44e729efa121ac9e',
           'queries':'aca3680890b1c2ff15db90bc25ba99ceb661086b3a0269421c056c4a723c72e0'}


def load_split(name, download):
    import pyarrow.parquet as pq
    path = CACHE/'doris'/(name+'.parquet')
    if not path.is_file() and download:
        path.parent.mkdir(parents=True,exist_ok=True)
        with urlopen(f'{SOURCE}/resolve/{REVISION}/data/{name}/test-00000.parquet?download=true',timeout=120) as response:
            data = response.read(8_000_001)
        if hashlib.sha256(data).hexdigest()!=DIGESTS[name]:
            raise ValueError('Unexpected dataset content for '+name)
        path.write_bytes(data)
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=DIGESTS[name]:
        raise ValueError('Missing or incorrect dataset file: '+str(path))
    return pq.read_table(path).to_pylist()


def metrics(ranked, grades):
    def dcg(gains):
        return sum(score/log2(i+2) for i,score in enumerate(gains))
    ordered = [grades[p['paperId']] for p in ranked[:10]]
    ideal = sorted(grades.values(),reverse=True)
    best = ideal[0]
    return {'nDCG@10':dcg(ordered)/dcg(ideal[:10]), 'best_grade_Recall@10':ordered.count(best)/ideal.count(best)}


def benchmark(download,device):
    docs = {r['_id']:r['text'] for r in load_split('corpus',download)}
    judgments = defaultdict(dict)
    for row in load_split('default',download):
        judgments[row['query-id']][row['corpus-id']] = row['score']
    previous = historic(PREVIOUS)
    ranker = Ranker(device)
    rows = []
    for q in load_split('queries',download):
        qid, text = q['_id'], q['text']
        grades = judgments[qid]
        papers = [dict(paperId=key,abstract=docs[key],title='') for key in sorted(grades)]
        case = dict(qid=qid,facet='doris',question=text,papers=papers)
        semantic = score_case(ranker,case,device)
        # Use the same short rewrite for both systems without consulting candidates or labels.
        plan = {'topic_queries':[' '.join(text.split()[:12])], 'dimensions':[]}
        length = len(' '.join(text.split()))
        row = {'qid':qid,'chars':length,'pool':len(papers),
               'passage_matching':length>300 and retrieval.method_passage_intent(text)}
        for key,rank in [('previous',previous),('current',fuse_rankings)]:
            row[key] = metrics(rank(text,semantic,plan),grades)
        with patch.object(retrieval,'method_passage_intent',return_value=True):
            row['all_long_questions_use_passages'] = metrics(fuse_rankings(text,semantic,plan),grades)
        rows.append(row)
    summary = {system:{metric:round(mean(r[system][metric] for r in rows),5)
                       for metric in rows[0][system]} for system in ('previous','all_long_questions_use_passages','current')}
    intervals = {k:paired_interval(*[[{'qid':r['qid'],**r[side]} for r in rows]
                                     for side in ('previous','current')],k) for k in summary['current']}
    return {'baseline':PREVIOUS,'data':SOURCE+'/tree/'+REVISION,'data_sha256':DIGESTS,
            'ranker_source_sha256_lf':hashlib.sha256((ROOT/'clinkrag/retrieval.py').read_text(encoding='utf-8').encode()).hexdigest(),
            'protocol':'Every published BIRCO DORIS-MAE test query and its complete judged pool. The snapshot has abstracts without titles. Grade is the published aggregated aspect relevance (model-assisted), not expert method similarity. Linear-gain nDCG@10 and recall of all joint highest-grade items at 10. No generated planner or live provider ranking.',
            'queries':len(rows),'long_queries':sum(r['chars']>300 for r in rows),'pairs':sum(r['pool'] for r in rows),
            'queries_using_passages':sum(r['passage_matching'] for r in rows),
            'summary':summary,'paired_intervals':intervals,'cases':rows}


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download',action='store_true')
    parser.add_argument('--device',default='cuda:0')
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    report = benchmark(args.download,args.device)
    args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report['summary']))
