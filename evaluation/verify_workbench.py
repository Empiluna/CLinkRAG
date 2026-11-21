"""Optional live acceptance against public papers. Never uses private study history."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'longans')]
from clinkrag.library import load_library
from debug_ui.brief import make_brief
from debug_ui.literature import literature_search, ServiceUnavailable
from llms.settings import load_settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', required=True,
                        help='Allow up to 20 model calls on bundled public abstracts and 3 Crossref queries')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--model', help='Optional model ID on the already configured service')
    args = parser.parse_args()
    config = load_settings()
    if args.model:
        config['MODEL_NAME'] = args.model
    records = load_library()
    references = {p['paper_id']:p for p in records}
    chosen = {}
    for record in records:
        chosen.setdefault(record['field'], record)
    report = {'started_utc':datetime.now(timezone.utc).isoformat(), 'model':config.get('MODEL_NAME'),
              'protocol':'One built-in example per field; first registered paper per field, top 3 passages.',
              'briefs':[], 'crossref':[]}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    def save():
        args.out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    for query in ('interleaved mathematics practice', 'urban heat island tree canopy', 'bridge vibration damage detection'):
        try:
            result = literature_search({'collection':'crossref','question':query,'limit':3})
            items = result['items']
            ok = bool(items) and all(p['quote'] and p['url'].startswith('https://doi.org/') for p in items)
            report['crossref'].append({'query':query,'ok':ok,'searched':result['total'],
                                       'dois':[p['doi'] for p in items]})
        except ServiceUnavailable as exc:
            report['crossref'].append({'query':query,'ok':False,'error':str(exc)})
        save()
    for domain,paper in chosen.items():
        question = paper['example_question']
        passages = literature_search({'question':question, 'limit':3})['items']
        row = {'field':domain,'question':question,'expected_paper':paper['paper_id']}
        start = time.monotonic()
        try:
            brief = make_brief({'question':question,'items':passages},config)
            pairs = [(f['paper_id'],f['quote']) for f in brief['findings']]
            row.update(findings=brief['findings'], exact=bool(pairs) and all(q in references[pid]['text'] for pid,q in pairs),
                       expected_cited=any(pid==paper['paper_id'] for pid,_ in pairs))
        except (ServiceUnavailable,ValueError) as exc:
            row['error'] = str(exc)
        row['elapsed_seconds'] = round(time.monotonic()-start,1)
        report['briefs'].append(row)
        save()
        print(domain, row.get('error') or ('exact='+str(row.get('exact'))),flush=True)
        if row.get('error') and not any(r.get('exact') for r in report['briefs']):
            break  # Invalid credentials or unavailable initial service: avoid repeated charges.
    report['completed_domains']=sum(row.get('exact',False) for row in report['briefs'])
    save()
    return int(report['completed_domains'] != len(chosen) or not all(row['ok'] for row in report['crossref']))


if __name__=='__main__':
    raise SystemExit(main())
