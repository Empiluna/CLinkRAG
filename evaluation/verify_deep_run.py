"""Run one bounded real CLinkRAG study in isolation and audit its persisted artifacts."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from debug_ui.server import validate_request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', required=True, action='store_true',
                        help='Use configured Semantic Scholar, model API and local reranker')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    question = '间隔学习能否改善中学物理学习的保持效果？'
    request = validate_request({'question':question, 'method':'clinkrag_online','online_papers':3,
                                'research_dimensions':['中学物理学习的保持效果'], 'extra_queries':0,
                                'initial_papers':2, 'answer_words':500,'max_tokens':1800})
    start = time.monotonic()
    folder = ROOT/'.cache'/'acceptance'
    folder.mkdir(exist_ok=True,parents=True)
    with tempfile.TemporaryDirectory(dir=folder) as directory:
        job = Path(directory)
        (job/'request.json').write_text(json.dumps(request,ensure_ascii=False),encoding='utf-8')
        try:
            subprocess.run([sys.executable, str(ROOT/'debug_ui'/'worker.py'),directory], cwd=ROOT,
                           stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=300,
                           env={**os.environ,'PYTHONUTF8':'1'})
        except subprocess.TimeoutExpired:
            pass
        def read(name):
            path=job/name
            return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
        state, result, online = read('state.json'),read('result.json'),read('online-corpus.json')
        sources=result.get('sources',[])
        by_id={p['paperId']:p for p in online.get('papers',[])}
        cited={int(s) for s in re.findall(r'\[(\d+)\]',result.get('answer',''))}
        verified=bool(cited) and all(i<len(sources) and sources[i]['text'] in by_id.get(sources[i]['id'],{}).get('abstract','') for i in cited)
        report={'question':question,'method':request['method'],'elapsed_seconds':round(time.monotonic()-start,1),
                'state':state.get('status','timeout'),'error_type':state.get('error','')[:180],
                'query_count':len(online.get('queries',[])), 'candidate_count':len(online.get('candidates',[])),
                'selected_papers':len(by_id), 'cited_source_indices':sorted(cited),'cited_passages_match_abstract':verified,
                'has_separate_review':bool(result.get('evidence_review')),'answer':result.get('answer','')}
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(report['state'],'selected',len(by_id),'cited',len(cited))
        return int(not (report['state']=='success' and verified and report['has_separate_review']))


if __name__=='__main__':
    raise SystemExit(main())
