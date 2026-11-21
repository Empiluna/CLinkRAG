"""Evaluate the shipped lexical search on original BEIR test judgments. No model keys.
Run e.g. python -m evaluation.benchmark_public scifact nfcorpus arguana --download
Only aggregate metrics are published. Downloaded benchmark corpora stay under .cache.
"""
import argparse
import hashlib
import heapq
import io
import json
import math
from pathlib import Path
import time
import urllib.request
import zipfile

from clinkrag.library import key_terms
from clinkrag.retrieval import LexicalIndex, terms

ROOT=Path(__file__).resolve().parents[1]
DATASETS={'scifact','nfcorpus','arguana','fiqa'}
BASE='https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/'


def hf_archive(dataset):
    """Read BEIR's official HF organization mirror when university hosting is unavailable."""
    import pyarrow.parquet as pq
    import requests
    def get(url):
        response=requests.get(url,timeout=90)
        response.raise_for_status()
        return response
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as archive:
        def put(path, data):
            info=zipfile.ZipInfo(dataset+'/'+path)
            archive.writestr(info,data,compress_type=zipfile.ZIP_DEFLATED)
        for part in ['corpus','queries']:
            tree=get(f'https://huggingface.co/api/datasets/BeIR/{dataset}/tree/main/{part}').json()
            files=sorted(node['path'] for node in tree if node['path'].endswith('.parquet'))
            if not files:
                raise ValueError('No published parquet file: '+part)
            records=[]
            for path in files:
                body=get(f'https://huggingface.co/datasets/BeIR/{dataset}/resolve/main/{path}').content
                table=pq.read_table(io.BytesIO(body))
                for row in table.to_pylist():
                    record={k:row[k] for k in ('_id','title','text') if k in row}
                    record['_id']=str(record['_id'])
                    records.append(json.dumps(record,ensure_ascii=False))
            put(part+'.jsonl','\n'.join(records).encode('utf-8'))
        put('qrels/test.tsv',get(f'https://huggingface.co/datasets/BeIR/{dataset}-qrels/resolve/main/test.tsv').content)
    return buffer.getvalue()


def acquire(dataset, download, mirror):
    location=ROOT/'.cache'/'beir'/(dataset+'-'+mirror+'.zip')
    if location.exists():
        return location
    if not download:
        raise FileNotFoundError(f'{location.name} 尚未缓存，请使用 --download')
    location.parent.mkdir(parents=True,exist_ok=True)
    if mirror=='huggingface':
        content=hf_archive(dataset)
    else:
        with urllib.request.urlopen(BASE+dataset+'.zip',timeout=90) as response:
            content=response.read(150_000_001)
    if len(content)>150_000_000:
        raise ValueError('Benchmark archive exceeds 150 MB')
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        if dataset+'/qrels/test.tsv' not in archive.namelist():
            raise ValueError('Invalid BEIR archive')
    temporary=location.with_suffix('.tmp')
    temporary.write_bytes(content)
    temporary.replace(location)
    return location


def evaluate(dataset, download, mirror):
    archive_path=acquire(dataset, download, mirror)
    with zipfile.ZipFile(archive_path) as archive:
        def read_jsonl(name):
            with archive.open(dataset+'/'+name+'.jsonl') as stream:
                return [json.loads(line) for line in stream if line.strip()]
        corpus=read_jsonl('corpus')
        questions={q['_id']:q['text'] for q in read_jsonl('queries')}
        with archive.open(dataset+'/qrels/test.tsv') as stream:
            judgments={}
            next(stream)
            for line in stream:
                query,doc,grade=line.decode().strip().split('\t')
                if int(grade)>0:
                    judgments.setdefault(query,{})[doc]=int(grade)
    doc_ids=[p['_id'] for p in corpus]
    scores={}
    for mode in ('previous_lexical','abstract_search'):
        tokenizer=terms if mode=='previous_lexical' else key_terms
        title_weight=1 if mode=='previous_lexical' else 2
        documents=[' '.join([p.get('title','')]*title_weight+['',p.get('text','')]) for p in corpus]
        start=time.perf_counter()
        index=LexicalIndex(documents, tokenizer=tokenizer)
        metrics={'Hit@3':0.,'MRR@10':0.,'nDCG@10':0.,'Recall@100':0.}
        misses=0
        for qid,rels in judgments.items():
            row=index.scores(questions[qid])
            best=heapq.nlargest(101, (i for i,value in enumerate(row) if value>0), key=row.__getitem__)
            # ArguAna pairs arguments with counterarguments and excludes the query itself.
            ranked=[doc_ids[i] for i in best if doc_ids[i]!=qid][:100]
            grades=[rels.get(d,0) for d in ranked]
            metrics['Hit@3']+=any(grades[:3])
            metrics['MRR@10']+=next((1/n for n,r in enumerate(grades[:10],1) if r),0.)
            dcg=sum(r/math.log2(n+2) for n,r in enumerate(grades[:10]))
            ideal=sum(r/math.log2(n+2) for n,r in enumerate(sorted(rels.values(),reverse=True)[:10]))
            metrics['nDCG@10']+=dcg/ideal
            metrics['Recall@100']+=sum(bool(r) for r in grades)/len(rels)
            misses+=not any(grades[:3])
        scores[mode]={k:round(v/len(judgments),4) for k,v in metrics.items()} | {'misses_at_3':misses,'seconds':round(time.perf_counter()-start,2)}
    return {'dataset':dataset,'source':mirror,'documents':len(corpus),'queries':len(judgments),'archive_sha256':hashlib.sha256(archive_path.read_bytes()).hexdigest(),'scores':scores}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('datasets', nargs='+',choices=sorted(DATASETS))
    parser.add_argument('--download',action='store_true')
    parser.add_argument('--mirror',choices=['university','huggingface'],default='university')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    results=[]
    for dataset in args.datasets:
        result=evaluate(dataset,args.download,args.mirror)
        print(json.dumps(result,ensure_ascii=False), flush=True)
        results.append(result)
        if args.output:
            args.output.parent.mkdir(parents=True,exist_ok=True)
            args.output.write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
