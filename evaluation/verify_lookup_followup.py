"""Compare personal-library HTTP retrieval across versions. No model or provider calls."""
import argparse
from http.server import ThreadingHTTPServer
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from threading import Thread
from urllib.request import ProxyHandler, Request, build_opener
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
BASE = '0ec95bd2855784f4e4eb34bd6776a912f7451be6'
# These questions cannot be answered by any of the 36 machine learning abstracts.
# They probe whether translating ordinary words creates a spurious literature match.
OUTSIDE = (
    '如何从墓志铭的亲属称谓还原唐代姻亲关系？',
    '怎么从窑址出土的青瓷釉色判断烧造年代？',
    '莫扎特晚期弦乐四重奏如何使用转调？',
    '季风对茶树鲜叶的采收期有什么影响？',
    '什么决定毛衣洗涤后羊毛纤维的缩水程度？',
    '如何比较两种小提琴琴弦的音色与衰减时间？',
    '海水温度变化会怎样影响珊瑚幼体附着？',
    '哪种水彩颜料干燥后最能保持纸面透明感？',
    '植物的根毛在盐碱土壤中如何吸收水分？',
    '桦树年轮的宽度能否反映当地上世纪的降雨？',
    '越剧和昆曲的唱腔在换气上有哪些差异？',
    '怎么用瓷器底款和胎土辨别古代产地？',
)


def candidates(qid, keep, papers):
    # Keep the known paper and old top-three competitors. Fill remaining slots with
    # a stable hash sample, then order by opaque ID. The web form accepts 20 papers.
    pool = sorted(papers, key=lambda pid: hashlib.sha256((qid+'|'+pid).encode()).digest())
    selected = sorted(list(dict.fromkeys(keep + pool))[:20])
    return [papers[pid] for pid in selected]


def evaluate(version):
    sys.path[:0] = [str(version), str(version/'longans')]
    sys.path.append(str(ROOT/'evaluation'))
    from benchmark_cs_ai import arxiv_documents, QUESTIONS, read
    from debug_ui.model_settings import DEFAULTS, SettingsStore
    from debug_ui.server import Jobs, make_handler

    baseline_report = subprocess.check_output(['git','show',BASE+':evaluation/reports/cs_ai_quality.json'], cwd=ROOT)
    previous = json.loads(baseline_report)['known_queries']
    misses = {r['qid']:r['current']['top'] for r in previous
              if r['language'] == 'zh' and r['current']['rank10'] != 1}
    questions = [q for q in read(QUESTIONS)['questions'] if q['id'] in misses]
    assert len(questions)==9
    papers = {p['paper_id']:p for p in arxiv_documents()}
    rows, outside = [], []
    checked = 0
    with tempfile.TemporaryDirectory() as folder:
        jobs = Jobs(Path(folder))
        settings = SettingsStore(Path(folder)/'settings.yaml', loader=lambda:dict(DEFAULTS))
        handler = make_handler(jobs, 'isolated-retrieval-check', settings)
        with ThreadingHTTPServer(('127.0.0.1', 0), handler) as server:
            thread = Thread(target=server.serve_forever,daemon=True)
            thread.start()
            base = 'http://127.0.0.1:'+str(server.server_port)
            http = build_opener(ProxyHandler({}))

            def search(text, subset):
                payload = {'collection':'personal', 'question':text, 'papers':subset, 'limit':10}
                request = Request(base+'/api/literature/search', data=json.dumps(payload).encode(),
                                  headers={'Content-Type':'application/json','Origin':base,
                                           'X-SciRAG-Token':'isolated-retrieval-check'})
                with http.open(request,timeout=30) as response:
                    result = json.load(response)
                original = {p['url']:p for p in subset}
                ids = []
                for item in result['items']:
                    source = original[item['url']]
                    assert source['text'][item['start']:item['end']] == item['quote'] and item['quote']
                    assert item['url'] in result['markdown'] and item['url'] in result['ris']
                    ids.append(source['paper_id'])
                return ids

            try:
                for q in questions:
                    pool = candidates(q['id'], [q['target'], *misses[q['id']]], papers)
                    ranked = search(q['zh'], pool)
                    checked += len(ranked)
                    rows.append({'id':q['id'],'target':q['target'],'rank10':
                                 ranked.index(q['target'])+1 if q['target'] in ranked else None,
                                 'candidates':[p['paper_id'] for p in pool], 'top':ranked[:3]})
                pool = candidates('outside-computing', [], papers)
                for text in OUTSIDE:
                    ranked = search(text,pool)
                    checked += len(ranked)
                    outside.append({'question':text,'returned':len(ranked),'top':ranked[:3]})
            finally:
                server.shutdown()
                thread.join()
                jobs.close()
    return {'known_misses_on_20':rows, 'outside_domain':outside,
            'outside_domain_candidates':[p['paper_id'] for p in pool],
            'known_first':sum(r['rank10']==1 for r in rows),
            'outside_with_results':sum(bool(r['returned']) for r in outside), 'verified_excerpts':checked}


def worker(version):
    command = [sys.executable, '-I', str(Path(__file__).resolve()), '--worker', str(version)]
    return json.loads(subprocess.check_output(command))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker',type=Path,help=argparse.SUPPRESS)
    parser.add_argument('--output',type=Path)
    args = parser.parse_args()
    if args.worker:
        print(json.dumps(evaluate(args.worker)))
    else:
        with tempfile.TemporaryDirectory() as folder:
            old = Path(folder)
            archive = subprocess.check_output(['git','archive','--format=zip',BASE,'debug_ui','clinkrag','longans/llms'],cwd=ROOT)
            with ZipFile(io.BytesIO(archive)) as files:
                files.extractall(old)
            before = worker(old)
        after = worker(ROOT)
        report = {'baseline_commit':BASE, 'endpoint':'POST /api/literature/search, collection=personal, limit=10',
                  'protocol':'Fixed 20 documents per case, the same in both processes. This exercises the web form candidate limit. For original 36-paper ranks see the separate diagnostic report. The negative control asks out-of-domain questions of 20 computing abstracts and counts lists with at least one result.',
                  'previous':before,'current':after}
        if args.output:
            args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print({name:{k:report[name][k] for k in ('known_first','outside_with_results','verified_excerpts')}
               for name in ('previous','current')})
