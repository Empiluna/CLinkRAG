"""Run and record the bilingual, open-literature known-item check without network access."""
import argparse
import json
from pathlib import Path
from statistics import median
from time import perf_counter

from clinkrag.library import load_library, search_library
from clinkrag.retrieval import LexicalIndex, lexical_scores

ROOT=Path(__file__).resolve().parents[1]


def measure():
    papers=load_library()
    index=LexicalIndex([p['title']+'\n'+p['text'] for p in papers])
    by_id={p['paper_id']:p for p in papers}
    result=[]
    for suffix, en, zh in json.loads((ROOT/'evaluation/data/library_questions.json').read_text(encoding='utf-8')):
        target='10.1371/journal.pone.'+suffix
        for lang, query in [('en',en),('zh',zh)]:
            previous=index.scores(query)
            ablation=[papers[i]['paper_id'] for i in sorted(range(len(previous)),key=previous.__getitem__,reverse=True) if previous[i]>0]
            matches=search_library(query,limit=50)['items']
            current=[m['paper_id'] for m in matches]
            valid=all(by_id[m['paper_id']]['text'][m['start']:m['end']]==m['quote'] and bool(m['quote'].strip()) for m in matches)
            result.append({'question':query,'language':lang,'domain':by_id[target]['field'],'expected':target,
                           'previous_lexical_rank':ablation.index(target)+1 if target in ablation else None,
                           'local_rank':current.index(target)+1 if target in current else None,
                           'passages_checked':len(matches),'offsets_correct':valid})
    summary={}
    for lang in ('en','zh'):
        rows=[r for r in result if r['language']==lang]
        summary[lang]={}
        for key in ('previous_lexical_rank','local_rank'):
            ranks=[r[key] or 1000 for r in rows]
            summary[lang][key]={'Hit@1':sum(r<=1 for r in ranks)/len(rows),'Hit@3':sum(r<=3 for r in ranks)/len(rows),
                                'MRR@10':sum(1/r for r in ranks if r<=10)/len(rows)}
    # Same data, queries, tokenizer and scores. Isolate the cost of rebuilding
    # corpus statistics for every query versus sharing them across a batch.
    texts=[p['title']+'\n'+p['text'] for p in papers]
    queries=['ancient Egyptian chronology','radiocarbon dating','Old Kingdom chronology']
    rebuilt,shared=[],[]
    for _ in range(15):
        start=perf_counter()
        baseline=[lexical_scores(query,texts) for query in queries]
        rebuilt.append(perf_counter()-start)
        start=perf_counter()
        batch_index=LexicalIndex(texts)
        updated=[batch_index.scores(query) for query in queries]
        shared.append(perf_counter()-start)
        if updated!=baseline:
            raise AssertionError('Index reuse changed BM25 scores')
    timing={'runs':len(shared),'queries_per_batch':len(queries),'documents':len(texts),
            'rebuild_median_ms':round(median(rebuilt)*1000,3),
            'reuse_median_ms':round(median(shared)*1000,3),'identical_scores':True}
    return {'corpus_size':len(papers),'domains':sorted({p['field'] for p in papers}),
            'summary':summary,'index_reuse':timing,'queries':result}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    data=measure()
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(data['summary'],indent=2))
    if not all(r['offsets_correct'] for r in data['queries']):
        raise SystemExit('Detected a broken passage offset')
