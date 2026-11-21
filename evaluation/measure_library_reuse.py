"""Measure source lookup via the original and current public entry points; no network required."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import tempfile
from time import perf_counter

ROOT=Path(__file__).resolve().parents[1]
BASE='b0eb8e0b8652e57b7e187e0bfc42f40d25c806af'
MODULES=('clinkrag/__init__.py','clinkrag/library.py','clinkrag/retrieval.py','clinkrag/data/library.json',
         'debug_ui/__init__.py','debug_ui/literature.py')
QUERY_FILES=('evaluation/data/library_questions.json','evaluation/data/corpus.json')


def measure(fn,count):
    samples=[]
    for _ in range(count):
        start=perf_counter()
        fn()
        samples.append(round((perf_counter()-start)*1000,4))
    return {'runs':count,'median_ms':round(statistics.median(samples),3),
            'p95_ms':round(sorted(samples)[math.ceil(.95*len(samples))-1],3),'ms':samples}


def worker(root):
    sys.path.insert(0,str(root))
    from clinkrag import library
    from debug_ui.literature import literature_search

    questions=json.loads((ROOT/QUERY_FILES[0]).read_text(encoding='utf-8'))
    papers=json.loads((ROOT/QUERY_FILES[1]).read_text(encoding='utf-8'))['papers']
    selected=[row[1] for row in questions[:8]]
    requests=[{'question':q,'collection':'builtin','limit':5} for q in selected]
    queries=['Retrieval augmented generation','Self-RAG','retrievers for response factuality','query expansion']
    def fresh():
        if hasattr(library,'_bundled_index'):
            library._bundled_index.cache_clear()
        library._bundled.cache_clear()
        literature_search(requests[0])
    def warm():
        return [literature_search(r) for r in requests]
    def rerank():
        return [library.search_library(q,papers=papers,limit=5) for q in queries]

    cold=measure(fresh,15)
    warm()
    warm_times=measure(warm,35)
    rerank()
    supplied_times=measure(rerank,35)
    bundled={p['paper_id']:p['text'] for p in library.load_library()}
    supplied={p['id']:p['text'] for p in papers}
    checked=0
    for results,source in [(warm(),bundled),(rerank(),supplied)]:
        for result in results:
            assert result['items']
            for item in result['items']:
                assert item['quote'] and item['quote']==source[item['paper_id']][item['start']:item['end']]
                checked+=1
    return {'bundled_first_query':cold,'bundled_eight_warm_queries':warm_times,
            'supplied_four_independent_queries':supplied_times,'offsets_checked':checked}


def run(root):
    output=subprocess.check_output([sys.executable,'-I',str(Path(__file__).resolve()),'--worker',str(root)],
                                   text=True,encoding='utf-8')
    return json.loads(output)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker',type=Path,help=argparse.SUPPRESS)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.worker:
        print(json.dumps(worker(args.worker)))
        return
    with tempfile.TemporaryDirectory() as folder:
        old=Path(folder)
        for name in MODULES:
            dest=old/name
            dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes(subprocess.check_output(['git','show',BASE+':'+name],cwd=ROOT))
        before=run(old)
    after=run(ROOT)
    ratio={key:round(before[key]['median_ms']/after[key]['median_ms'],2)
           for key in before if isinstance(before[key],dict)}
    report={'baseline_commit':BASE,'python':platform.python_version(),'platform':platform.system(),
            'clock':'perf_counter; in-process wall time in milliseconds; separate interpreter per revision',
            'sources':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in QUERY_FILES},
            'fixture':{'bundled':'16 open abstracts; first eight English queries in library_questions.json',
                       'supplied':'28 existing frozen abstracts/snippets in evaluation/data/corpus.json, passed directly',
                       'cold':'Clear in-process collection and index before each single request. OS page cache and interpreter remain warm.',
                       'warm':'Eight calls to literature_search per sample, including excerpt selection and Markdown/RIS exports.',
                       'supplied_batch':'Four search_library calls with fresh input indexing; excludes remote provider and transport.',
                       'supplied_queries':['Retrieval augmented generation','Self-RAG','retrievers for response factuality','query expansion']},
            'before':before,'after':after,'median_speedup':ratio}
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'median_speedup':ratio, 'passage_offsets_checked':[before['offsets_checked'],after['offsets_checked']]},indent=2))


if __name__=='__main__':
    main()
