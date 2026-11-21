"""Sealed bilingual follow-up. Run as python -m evaluation.benchmark_followup_holdout.

Baseline code is read from Git. LitSearch needs pyarrow and the pinned parquet
snapshot prepared by benchmark_cs_ai; use --download to fetch a missing copy.
"""
import argparse
from collections import defaultdict
import hashlib
from io import BytesIO
import inspect
import json
from pathlib import Path
import random
from statistics import mean
import subprocess
import sys
import tempfile
from zipfile import ZipFile

if __package__:
    from . import litsearch_audit
else:
    import litsearch_audit

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = ROOT / 'evaluation/data/cs_ai_followup_holdout.json'
CACHE = ROOT / '.cache/cs-eval'
QUESTION_SHA = '2781c74149cc59e853cc2990b2b104dc60d7965f76993b5e600b6044f1d2a945'
CONFERENCE_SHA = '1ecc96c6664e0d193d7e50f8982c346855d570d20e789e5062a4304dab173c7a'
BASELINE_RESULT_SHA = 'cc56a96fffac80949ed41f969bc4dfd285e10ec4fcccde1f32a87d740f78c562'
DISTRACTOR_SEED = 'clinkrag-blind-followup-20261122-distractors:'
METRICS = ('Hit@1', 'Hit@3', 'MRR@10', 'Recall@10')


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def by_hash(ids, prefix):
    return sorted(ids, key=lambda paper_id: digest(prefix + paper_id))


def inputs():
    text = QUESTIONS.read_text(encoding='utf-8')
    if digest(text) != QUESTION_SHA:
        raise ValueError('Frozen bilingual question file changed.')
    return json.loads(text)


def litsearch_inputs(fixture):
    import pyarrow.parquet as pq

    source = CACHE / 'litsearch'
    questions = {r['_id']: r['text'] for r in pq.read_table(source/'queries.parquet').to_pylist()}
    relevant = defaultdict(set)
    for row in pq.read_table(source/'qrels.parquet').to_pylist():
        if row['score'] > 0:
            relevant[row['query-id']].add(row['corpus-id'])
    docs = {}
    for batch in pq.ParquetFile(source/'corpus.parquet').iter_batches():
        for row in batch.to_pylist():
            if (row['title'] or '').strip() and (row['text'] or '').strip():
                docs[row['_id']] = dict(paper_id=row['_id'], title=row['title'], text=row['text'])
    seeds = fixture['sample_seeds']
    eligible = [qid for qid, targets in relevant.items() if targets <= docs.keys()]
    previous = set(by_hash(eligible, seeds['previous_litsearch'])[:100])
    sampled = by_hash(set(eligible)-previous, seeds['litsearch'])[:20]
    assert sampled == [row['id'] for row in fixture['litsearch']]
    known_positives = set.union(*relevant.values()) & docs.keys()
    distractors = by_hash(docs.keys()-known_positives, DISTRACTOR_SEED)[:2048]
    papers = {pid:docs[pid] for pid in sorted(known_positives | set(distractors))}
    prompts = [(r['id'], r['zh'], questions[r['id']], sorted(relevant[r['id']])) for r in fixture['litsearch']]
    return papers, prompts, len(known_positives), len(distractors)


def proceedings_inputs(code_root, fixture):
    content = (code_root/'clinkrag/data/computing.jsonl').read_text(encoding='utf-8')
    assert digest(content) == CONFERENCE_SHA
    rows = {p['paper_id']:p for p in map(json.loads, content.splitlines())}
    by_venue = defaultdict(list)
    for paper in rows.values():
        by_venue[paper['container']].append(paper['paper_id'])
    selected = [pid for venue in sorted(by_venue)
                for pid in by_hash(by_venue[venue], fixture['sample_seeds']['proceedings'])[:2]]
    assert selected == [entry['target'] for entry in fixture['proceedings']]
    prompts = [('conf-' + str(i), row['zh'], row['en'], [row['target']])
               for i,row in enumerate(fixture['proceedings'], 1)]
    return rows, prompts


def worker(code_root):
    sys.path.insert(0, str(code_root))
    from clinkrag.library import search_library
    from debug_ui.literature import literature_search

    for function, relative_path in [(search_library, 'clinkrag/library.py'),
                                    (literature_search, 'debug_ui/literature.py')]:
        assert Path(inspect.getfile(function)).resolve() == (code_root/relative_path).resolve()
    fixture = inputs()
    volumes, conference_queries = proceedings_inputs(code_root, fixture)
    library, official_queries, positives, distractors = litsearch_inputs(fixture)
    papers = list(library.values())
    rows = []
    for panel, prompts, sources in [('litsearch', official_queries, library),
                                    ('proceedings', conference_queries, volumes)]:
        for qid, zh, en, targets in prompts:
            for lang, text in [('zh',zh),('en',en)]:
                if panel == 'proceedings':
                    result = literature_search({'collection':'computing','question':text,'limit':10})
                else:
                    result = search_library(text, papers=papers, limit=10)
                assert result['total'] == len(sources)
                ids = []
                for item in result['items']:
                    source = sources[item['paper_id']]
                    assert item['quote'] and item['quote'] == source['text'][item['start']:item['end']]
                    ids.append(item['paper_id'])
                assert len(set(ids)) == len(ids)
                positions = [i for i,pid in enumerate(ids,1) if pid in targets]
                rank = min(positions, default=None)
                rows.append({'panel': panel, 'qid':qid, 'lang':lang, 'gold':targets, 'top10':ids,
                             'first_rank':rank, 'Hit@1':int(rank==1),
                             'Hit@3':int(rank is not None and rank<=3),
                             'MRR@10':1/rank if rank else 0, 'Recall@10':len(positions)/len(targets)})
    return {'scores':rows, 'complete_offsets_checked':sum(len(row['top10']) for row in rows),
            'litsearch_pool':{'official_positive_papers':positives, 'extra_random_papers':distractors,
                              'ids_sha256':digest('\n'.join(library))},
            'conference_papers':len(volumes), 'conference_sha256_lf':CONFERENCE_SHA,
            'ranker_source_sha256_lf':{f.relative_to(code_root).as_posix():digest(f.read_text(encoding='utf-8'))
                                      for f in sorted((code_root/'clinkrag').glob('*.py'))}}


def write(path, result):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')


def measure(code_root, output):
    subprocess.run([sys.executable, str(Path(__file__).resolve()), '--worker', str(code_root),
                    '--output', str(output)], check=True, cwd=ROOT)
    return json.loads(output.read_text(encoding='utf-8'))


def compare(a, b):
    assert [r['gold'] for r in a['scores']] == [r['gold'] for r in b['scores']]
    assert a['litsearch_pool'] == b['litsearch_pool']
    summary = []
    for panel in ('litsearch','proceedings'):
        for lang in ('zh','en'):
            before = [r for r in a['scores'] if r['panel']==panel and r['lang']==lang]
            after = [r for r in b['scores'] if r['panel']==panel and r['lang']==lang]
            assert [r['qid'] for r in before] == [r['qid'] for r in after]
            metrics = {}
            for metric in METRICS:
                delta = [y[metric]-x[metric] for x,y in zip(before,after,strict=True)]
                # One observation per distinct intent in each cell. Chinese and English
                # variants of the same intent are never counted twice in an interval.
                rng = random.Random(154902)
                boot = sorted(mean(rng.choices(delta, k=len(delta))) for _ in range(5000))
                metrics[metric] = {
                    'before':round(mean(r[metric] for r in before),4),
                    'after':round(mean(r[metric] for r in after),4),
                    'delta':round(mean(delta),4), 'paired_95_interval':[round(boot[124],4),round(boot[4874],4)],
                    'improved':sum(d>0 for d in delta), 'regressed':sum(d<0 for d in delta)}
            summary.append({'panel':panel,'language':lang,'intents':len(before),'metrics':metrics})
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--download', action='store_true')
    parser.add_argument('--baseline-only', action='store_true')
    parser.add_argument('--worker', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        write(args.output, worker(args.worker))
        return
    fixture = inputs()
    litsearch_audit.acquire(CACHE, args.download)
    with tempfile.TemporaryDirectory(dir=CACHE) as tmp:
        folder = Path(tmp)
        archive = subprocess.check_output(['git','archive','--format=zip',fixture['baseline'],
                                           'clinkrag','debug_ui'], cwd=ROOT)
        old = folder/'baseline'
        with ZipFile(BytesIO(archive)) as snapshot:
            snapshot.extractall(old)
        before = measure(old, folder/'before.json')
        if hashlib.sha256((folder/'before.json').read_bytes()).hexdigest() != BASELINE_RESULT_SHA:
            raise ValueError('Archived baseline rankings, inputs or source hashes differ from the sealed run.')
        if args.baseline_only:
            write(args.output, before)
            print('Baseline sealed', hashlib.sha256(args.output.read_bytes()).hexdigest())
            return
        after = measure(ROOT, folder/'after.json')
    result = {'baseline_commit':fixture['baseline'], 'frozen_prompts_sha256_lf':QUESTION_SHA,
              'sealed_baseline_sha256':BASELINE_RESULT_SHA,
              'additional_current_resource_sha256':{
                  f.relative_to(ROOT).as_posix():hashlib.sha256(f.read_bytes()).hexdigest()
                  for f in sorted((ROOT/'clinkrag/data').iterdir())
                  if f.is_file() and f.suffix not in ('.json', '.jsonl', '.gz')},
              'provenance':{'litsearch':'https://aclanthology.org/2024.emnlp-main.840/',
                            'metadata_revision':litsearch_audit.REVISION,
                            'parquet_sha256':litsearch_audit.FILES},
              'protocol':('20 official LitSearch intents disjoint from the first published 100, original English '
                          'and Chinese rewrites with unchanged official labels. Rank in the shared positive pool '
                          'plus 2,048 fixed extra searchable papers drawn by SHA-256 from other corpus records. '
                          '14 new intents based on two hash-sampled abstracts per venue use all 1,052 proceedings '
                          'as competitors. Known-item scores give no credit for alternate relevant unjudged papers. '
                          'Different candidate pools and label sources are reported separately. This is a fixed '
                          'diagnostic sample, not a full-corpus leaderboard or a population-wide estimate.'),
              'summary':compare(before,after), 'before':before,'after':after}
    write(args.output, result)
    for row in result['summary']:
        print(row['panel'],row['language'],{k:(v['before'],v['after']) for k,v in row['metrics'].items()})


if __name__ == '__main__':
    main()
