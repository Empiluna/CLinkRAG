"""Compare the actual local search API on fixed CS/AI questions and expert CSFCube judgments.

First run: python evaluation/benchmark_cs_ai.py --download --litsearch --output evaluation/reports/cs_ai_quality.json
Subsequent runs are offline. Only metrics and IDs are redistributed, not third-party abstracts.
The optional LitSearch check requires pyarrow. Comparison requires the baseline commit in a git checkout.
"""
import argparse
import hashlib
import io
import json
import math
from pathlib import Path
from random import Random
import subprocess
import sys
import tempfile
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zipfile import ZipFile

if __package__:
    from . import litsearch_audit
else:
    import litsearch_audit

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / '.cache' / 'cs-eval'
QUESTIONS = ROOT / 'evaluation' / 'data' / 'cs_ai_queries.json'
BASELINE = 'b0eb8e0b8652e57b7e187e0bfc42f40d25c806af'
DATACITE_DIGEST = '91aa2da8162a11f79d0472309b03b73b4b18623274478c8f4f02775712ca62ff'
FACETS = ('background', 'method', 'result')
CSFCUBE_REV = '7ffe012c1d92c470f185fc086086caf5b8e05ef3'
CSFCUBE_FILES = {
    'abstracts-csfcube-preds.jsonl': '9d2d9414574b6e91d2487d3396d3256577149dad859e9f6eb231b95c2ba5577c',
    'test-pid2anns-csfcube-background.json': '2015cbf965377374e020b0ec133351ec1feb731b9a9c40da0e446ef6eee4fa5e',
    'test-pid2anns-csfcube-method.json': '4d9b48f4b6a7a4fc24a30e0c0e74d1cc53eb4214ec4b855e3cd98e86829323a2',
    'test-pid2anns-csfcube-result.json': '5ed7a63bc20e3deb725f8ec82abfcb1c5d79673befc942509b48effceb3be031',
}


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def checksum(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


def acquire(download):
    CACHE.mkdir(parents=True, exist_ok=True)
    for name, digest in CSFCUBE_FILES.items():
        path = CACHE / name
        if not path.exists() and download:
            url = f'https://raw.githubusercontent.com/iesl/CSFCube/{CSFCUBE_REV}/{name}'
            with urlopen(url, timeout=60) as response:
                content = response.read(8_000_001)
            if hashlib.sha256(content).hexdigest() != digest:
                raise ValueError(f'Unexpected CSFCube snapshot: {name}')
            path.write_bytes(content)
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError(f'Missing or modified {name}. Use --download with a clean cache.')
    raw = CACHE / 'datacite-raw.json'
    if not raw.exists():
        if not download:
            raise ValueError('Missing DataCite metadata: use --download once.')
        ids = read(QUESTIONS)['paper_ids']
        expr = 'doi:(' + ' OR '.join('10.48550/arxiv.' + id_ for id_ in ids) + ')'
        url = 'https://api.datacite.org/dois?' + urlencode({'page[size]':len(ids), 'query':expr})
        with urlopen(Request(url, headers={'User-Agent':'CLinkRAG-evaluation/1'}), timeout=60) as response:
            rows = json.load(response)['data']
        if len(rows) != len(ids):
            raise ValueError('Incomplete DataCite response.')
        raw.write_text(json.dumps(rows, ensure_ascii=False), encoding='utf-8')


def arxiv_documents():
    docs = {}
    for row in read(CACHE / 'datacite-raw.json'):
        doi = row['id'].lower()
        pid = doi.removeprefix('10.48550/arxiv.')
        attr = row['attributes']
        abstract = next(d['description'] for d in attr['descriptions'] if d['descriptionType'] == 'Abstract')
        docs[pid] = {'paper_id':pid, 'title':attr['titles'][0]['title'], 'text':abstract,
                     'doi':doi, 'url':'https://arxiv.org/abs/' + pid, 'year':attr['publicationYear']}
    if set(docs) != set(read(QUESTIONS)['paper_ids']):
        raise ValueError('DataCite paper IDs differ from the frozen candidate list.')
    ordered = [docs[pid] for pid in sorted(docs)]
    if checksum(ordered) != DATACITE_DIGEST:
        raise ValueError('DataCite metadata has changed, so this corpus cannot reproduce the frozen comparison.')
    return ordered


def run_query(search, query, papers, limit):
    items = search(query, papers=papers, limit=limit)['items']
    docs = {p['paper_id']:p['text'] for p in papers}
    for item in items:
        text = docs[item['paper_id']]
        if not item['quote'].strip() or text[item['start']:item['end']] != item['quote']:
            raise ValueError('Invalid original passage offset in ' + item['paper_id'])
    ranks = [r['paper_id'] for r in items]
    if len(ranks) != len(set(ranks)):
        raise ValueError('Duplicate paper in results.')
    return ranks


def known_items(search, papers):
    rows = []
    for q in read(QUESTIONS)['questions']:
        for lang in ('zh', 'en'):
            ranked = run_query(search, q[lang], papers, 10)
            rank = ranked.index(q['target']) + 1 if q['target'] in ranked else None
            rows.append({'qid':q['id'], 'language':lang, 'field':q['field'], 'kind':q['kind'],
                         'rank10':rank, 'top':ranked[:3]})
    return rows


def csfcube(search):
    source = [json.loads(line) for line in (CACHE / 'abstracts-csfcube-preds.jsonl').read_text(encoding='utf-8').splitlines()]
    meta = {r['paper_id']: r for r in source}
    docs = {pid:{'paper_id':pid, 'title':r['title'], 'text':' '.join(r['abstract'])} for pid,r in meta.items()}
    rows = []
    for facet in FACETS:
        pools = read(CACHE / f'test-pid2anns-csfcube-{facet}.json')
        for pid,pool in pools.items():
            r = meta[pid]
            terms = [s for s,label in zip(r['abstract'], r['pred_labels']) if label == facet + '_label']
            query = ' '.join([r['title'], *(terms or r['abstract'])])
            judgments = dict(zip(pool['cands'],pool['relevance_adju'],strict=True))
            # Sort by opaque ID so that a tie cannot exploit a relevance-sorted annotation file.
            candidates = [docs[id_] for id_ in sorted(judgments)]
            ranked = run_query(search, query, candidates, 10)
            grades = [judgments[id_] for id_ in ranked]
            ideal = sorted(judgments.values(), reverse=True)[:10]
            def dcg(values):
                return sum((2**g-1) / math.log2(i+2) for i,g in enumerate(values))
            positives = sum(g>=2 for g in judgments.values())
            rows.append({'qid':pid, 'facet':facet, 'pool':len(judgments), 'positives':positives,
                         'nDCG@10':round(dcg(grades)/dcg(ideal), 6),
                         'Recall@10':round(sum(g>=2 for g in grades)/positives, 6) if positives else None,
                         'Hit@3':int(any(g>=2 for g in grades[:3])),
                         'fallback_to_full_abstract':not terms})
    return rows


def aggregate(rows, known=False):
    if known:
        ranks = [r['rank10'] or 1000 for r in rows]
        return {'n':len(rows), 'Hit@1':round(sum(r==1 for r in ranks)/len(rows), 4),
                'Hit@3':round(sum(r<=3 for r in ranks)/len(rows), 4),
                'MRR@10':round(sum(1/r for r in ranks if r<=10)/len(rows), 4)}
    result = {'n':len(rows)}
    for key in ('nDCG@10','Hit@3','Recall@10'):
        values = [r[key] for r in rows if r[key] is not None]
        result[key] = round(sum(values)/len(values), 4)
    return result


def paired_interval(previous, current, field):
    """Resample query paper / intention IDs so repeated facets stay together."""
    groups = {}
    for old, new in zip(previous, current, strict=True):
        if old['qid'] != new['qid']:
            raise ValueError('Query order differs across the two evaluations.')
        if field == 'Hit@1':
            delta = int(new['rank10'] == 1) - int(old['rank10'] == 1)
        else:
            delta = new[field] - old[field]
        groups.setdefault(old['qid'], []).append(delta)
    rng = Random(312743)
    clusters = list(groups.values())
    draws = []
    for _ in range(2000):
        sample = [value for cluster in rng.choices(clusters, k=len(clusters)) for value in cluster]
        draws.append(sum(sample)/len(sample))
    draws.sort()
    return {'metric':field,'resampling_units':len(clusters),'paired_percentile_95_interval':
            [round(draws[49],4), round(draws[1949],4)]}


def worker(code_root, output, litsearch):
    sys.path.insert(0, str(code_root))
    from clinkrag.library import search_library
    papers = arxiv_documents()
    checked = 0
    def measured_search(*args, **kwargs):
        nonlocal checked
        response = search_library(*args, **kwargs)
        checked += len(response['items'])
        return response

    known = known_items(measured_search, papers)
    pools = csfcube(measured_search)
    summary = {lang:aggregate([row for row in known if row['language']==lang], True) for lang in ('zh','en')}
    metrics = {'all':aggregate(pools)}
    metrics.update({f:aggregate([r for r in pools if r['facet']==f]) for f in FACETS})
    result = {'known_summary':summary, 'expert_summary':metrics, 'known':known,'expert':pools}
    if litsearch:
        result['litsearch'] = litsearch_audit.evaluate(CACHE,measured_search,run_query)
    result['checked_excerpts'] = checked
    files = ('library.py','retrieval.py','technical.py','paper_ids.py')
    result['ranking_source_sha256'] = {
        name:hashlib.sha256((code_root/'clinkrag'/name).read_text(encoding='utf-8').encode()).hexdigest()
        for name in files if (code_root/'clinkrag'/name).exists()}
    output.write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')


def compare(args):
    acquire(args.download)
    if args.litsearch:
        litsearch_audit.acquire(CACHE,args.download)
    with tempfile.TemporaryDirectory(dir=CACHE) as directory:
        temp = Path(directory)
        archive = subprocess.check_output(['git','archive','--format=zip',BASELINE,'clinkrag'], cwd=ROOT)
        with ZipFile(io.BytesIO(archive)) as frozen:
            frozen.extractall(temp)
        results = {}
        for name, code_root in [('previous',temp),('current',ROOT)]:
            out = temp / (name+'.json')
            command = [sys.executable, str(Path(__file__).resolve()), '--worker', str(code_root),'--output', str(out)]
            if args.litsearch:
                command.append('--litsearch')
            subprocess.run(command, check=True)
            results[name] = read(out)
    previous,current = results['previous'],results['current']
    report = {'baseline_commit':BASELINE,'interface':'clinkrag.library.search_library',
              'known_item_source':'DataCite arXiv DOI metadata; English titles and abstracts, no added keywords',
              'known_item_documents':len(arxiv_documents()),'normalized_documents_sha256':checksum(arxiv_documents()),
              'query_sha256':checksum(read(QUESTIONS)), 'source_revision':CSFCUBE_REV,
              'csfcube_source':'https://github.com/iesl/CSFCube',
              'csfcube_protocol':'Each facet query uses the title and author-released automatically labeled sentences (full abstract fallback). Sorted judged pool IDs; no self augmentation. Exponential gain nDCG; relevance grade >=2 for Hit and Recall.',
              'known_summary':{n:r['known_summary'] for n,r in results.items()},
              'expert_summary':{n:r['expert_summary'] for n,r in results.items()},
              'ranking_source_sha256_lf':{n:r['ranking_source_sha256'] for n,r in results.items()},
              'verified_excerpts':{n:r['checked_excerpts'] for n,r in results.items()},
              'all_returned_passage_offsets_checked':True}
    report['paired_intervals'] = {
        lang:paired_interval([r for r in previous['known'] if r['language']==lang],
                             [r for r in current['known'] if r['language']==lang], 'Hit@1')
        for lang in ('zh','en')}
    report['paired_intervals']['expert'] = paired_interval(previous['expert'], current['expert'], 'nDCG@10')
    report['paired_intervals']['method'] = ('2,000 deterministic paired bootstrap replicates; '
        'known items clustered by original intent, CSFCube facets by original query paper ID. '
        'Deliberately selected known items do not represent a random sample of CS questions.')
    for mode in ('known','expert'):
        pairs = []
        for old,new in zip(previous[mode],current[mode],strict=True):
            if (old['qid'],old.get('language'),old.get('facet'))!=(new['qid'],new.get('language'),new.get('facet')):
                raise AssertionError('Mismatched query IDs')
            metrics = ('rank10','top') if mode=='known' else ('nDCG@10','Recall@10','Hit@3')
            pairs.append({k:v for k,v in new.items() if k not in metrics} |
                         {'previous':{k:old[k] for k in metrics}, 'current':{k:new[k] for k in metrics}})
        report[mode+'_queries'] = pairs
    if args.litsearch:
        report['litsearch'] = litsearch_audit.report({n:r['litsearch'] for n,r in results.items()},
                                                    aggregate,paired_interval)
    if args.output:
        args.output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('known_summary','expert_summary')},indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download',action='store_true')
    parser.add_argument('--litsearch',action='store_true',help='Also evaluate a fixed LitSearch slice; requires pyarrow.')
    parser.add_argument('--worker',type=Path,help=argparse.SUPPRESS)
    parser.add_argument('--output',type=Path)
    args = parser.parse_args()
    if args.worker:
        worker(args.worker,args.output,args.litsearch)
    else:
        compare(args)
