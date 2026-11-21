"""Replay the original Chinese misses against the last release and inspect ranking signals."""
import argparse
import hashlib
import io
import json
from pathlib import Path
from statistics import median
import subprocess
import sys
import tempfile
from time import perf_counter
from zipfile import ZipFile

if __package__:
    from . import benchmark_cs_ai as fixture
else:
    import benchmark_cs_ai as fixture

BASE = '0ec95bd2855784f4e4eb34bd6776a912f7451be6'
ROOT = fixture.ROOT
DIAGNOSTIC_NEGATIVES = (
    '地质学家如何测量火山碎屑沉积物的年龄', '豇豆通过什么方式固定土壤中的氮', '如何评价中世纪欧洲行会对城市艺术家的作用',
    '怀孕时血红蛋白下降是否需要额外补铁', '何种方法能抑制城市热岛效应', '核桃蛋白粉如何制作',
    '低温超导体在磁场中的阻抗变化', '怎样弹奏钢琴琶音能让乐句更连贯', '土壤碳储量具有哪些季节性变化',
    '湖泊富营养化如何改变藻类群落','西班牙风格小吃配方的口感与风味'
)


def run(code):
    sys.path.insert(0,str(code))
    from clinkrag.library import LibraryIndex, _query, search_library
    papers = fixture.arxiv_documents()
    index = LibraryIndex(papers)
    positions = {p['paper_id']:i for i,p in enumerate(papers)}
    config = fixture.read(fixture.QUESTIONS)['questions']
    bilingual = {(q['id'],lang):search_library(q[lang],papers,len(papers))['items']
                 for q in config for lang in ('zh','en')}
    checked = 0
    for items in bilingual.values():
        for item in items:
            assert papers[positions[item['paper_id']]]['text'][item['start']:item['end']]==item['quote']
            checked += 1
    signals = []
    for q in config:
        target = q['target']
        items = bilingual[q['id'],'zh']
        english = bilingual[q['id'],'en']
        ids = [r['paper_id'] for r in items]
        en_ids = [r['paper_id'] for r in english]
        target_rank = ids.index(target)+1 if target in ids else None
        _,topics,symbols,_ = _query(q['zh'])
        signal = {'id':q['id'], 'question':q['zh'], 'expected_id':target,
                  'expected_title':papers[positions[target]]['title'],
                  'rank':target_rank,'english_rank':en_ids.index(target)+1 if target in en_ids else None,
                  'winner':items[0]['title'] if items else None, 'winner_id':ids[0] if ids else None,
                  'winner_score':items[0]['score'] if items else None,
                  'expected_score':items[target_rank-1]['score'] if target_rank else 0,
                  'results_count':len(items),'curated_query_concepts':sorted(topics|symbols)}
        if (code/'clinkrag/cross_language.py').is_file():
            from clinkrag.cross_language import chinese_glosses, gloss_matches
            evidence = gloss_matches(index.full,chinese_glosses(q['zh']),index.rows).get(positions[target])
            signal['target_matched_english_groups'] = [words for _,words in evidence.hits] if evidence else []
        signals.append(signal)

    # Repeated, in-process batch over the same already built 36-paper index.
    # This measures the real effort to rank and extract quotes with the richer query.
    durations = []
    for _ in range(9):
        start = perf_counter()
        for q in config:
            index.search(q['zh'],limit=5)
        durations.append(round((perf_counter()-start)*1000,3))
    return {'cases':signals,'excerpt_offsets_checked':checked,
            'repeated_24_chinese_queries_ms':durations,'batch_median_ms':median(durations),
            'unrelated_queries_in_development':{
                q:[item['paper_id'] for item in search_library(q,papers,5)['items']] for q in DIAGNOSTIC_NEGATIVES}}


def main(args):
    fixture.acquire(args.download)
    with tempfile.TemporaryDirectory(dir=fixture.CACHE) as folder:
        path = Path(folder)
        archive = subprocess.check_output(['git','archive','--format=zip',BASE,'clinkrag'],cwd=ROOT)
        ZipFile(io.BytesIO(archive)).extractall(path)
        results = {}
        for label,code in [('previous',path),('current',ROOT)]:
            out=path/(label+'.json')
            subprocess.run([sys.executable,str(Path(__file__).resolve()),'--worker',str(code),'--output',str(out)],
                           cwd=ROOT,check=True)
            results[label]=fixture.read(out)
    previous = results['previous']['cases']
    current = results['current']['cases']
    misses = [a['id'] for a in previous if a['rank']!=1]
    timing = {k:{field:v[field] for field in ('batch_median_ms','repeated_24_chinese_queries_ms')}
              for k,v in results.items()}
    report={'baseline_commit':BASE,'fixed_corpus_sha256':fixture.checksum(fixture.arxiv_documents()),
            'question_sha256':fixture.checksum(fixture.read(fixture.QUESTIONS)),
            'protocol':'Git archive and working tree loaded in separate interpreters. Same public search_library on 36 frozen English records. All ranks include the full pool and null means no match. Known original questions and added unrelated diagnostics were used during development, so they are not blind tests.',
            'all_original_zh_top1':{k:sum(c['rank']==1 for c in v['cases']) for k,v in results.items()},
            'all_original_en_top1':{k:sum(c['english_rank']==1 for c in v['cases']) for k,v in results.items()},
            'original_misses':misses,'newly_missed':[b['id'] for a,b in zip(previous,current,strict=True) if a['rank']==1 and b['rank']!=1],
            'source_offsets_checked':{k:v['excerpt_offsets_checked'] for k,v in results.items()},
            'cases':[{'previous':a,'current':b} for a,b in zip(previous,current,strict=True)],
            'development_unrelated_queries':{k:v['unrelated_queries_in_development'] for k,v in results.items()},
            'timing_protocol':'Median of nine warm batches of 24 original Chinese questions, top five requested from the same 36-paper LibraryIndex. Includes ranking and quote extraction; excludes HTTP, construction and imports.',
            'timing':timing,'source_digest':{
                name:hashlib.sha256((ROOT/name).read_bytes() if name.endswith('.idx') else (ROOT/name).read_text(encoding='utf8').encode()).hexdigest()
                for name in ('clinkrag/library.py','clinkrag/cross_language.py','clinkrag/data/cedict-glosses.idx','clinkrag/data/technical-names.tsv')}}
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(report['all_original_zh_top1'],report['all_original_en_top1'])
    print('Timing', {k:v['batch_median_ms'] for k,v in timing.items()})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker',type=Path,help=argparse.SUPPRESS)
    parser.add_argument('--download',action='store_true')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.worker:
        args.output.write_text(json.dumps(run(args.worker),ensure_ascii=False),encoding='utf8')
    else:
        main(args)
