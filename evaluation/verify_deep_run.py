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
    parser.add_argument('--case', choices=('education','computing','image-matching'), default='education')
    args = parser.parse_args()
    question = '间隔学习能否改善中学物理学习的保持效果？'
    dimension = '中学物理学习的保持效果'
    if args.case == 'computing':
        question = 'BERT（DOI:10.18653/v1/N19-1423）怎样预训练双向语言表示，原论文摘要给出了哪些结果？'
        dimension = 'BERT 的双向预训练与原论文结果'
    elif args.case == 'image-matching':
        question = '哪篇原始论文把有方向的快速角点和经过旋转的二进制描述子结合起来，用于实时图像匹配？原作者怎样比较速度和旋转鲁棒性？'
        dimension = '局部图像特征的速度与旋转鲁棒性'
    request = validate_request({'question':question, 'method':'clinkrag_online','online_papers':3,
                                'research_dimensions':[dimension], 'extra_queries':0,
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
        named_cited = True
        if args.case == 'computing':
            requested = online.get('requested_references',{})
            named = requested.get('DOI:10.18653/v1/n19-1423')
            named_cited = bool(named and any(i<len(sources) and sources[i]['id']==named for i in cited))
            report.update(requested_references=requested, named_paper_used_in_answer=named_cited,
                          selected_titles=[p['title'] for p in by_id.values()])
        elif args.case == 'image-matching':
            # Keep the adjudication DOI entirely outside the question, planner and worker.
            target = '10.1109/iccv.2011.6126544'
            candidates = online.get('candidates',[])
            target_ids = {p['paperId'] for p in candidates
                          if str((p.get('externalIds') or {}).get('DOI','')).lower()==target}
            named_cited = any(i<len(sources) and sources[i]['id'] in target_ids for i in cited)
            report.update(expected_doi=target, target_in_candidates=bool(target_ids),
                          target_selected=bool(target_ids.intersection(by_id)), target_cited=named_cited,
                          selected_titles=[p['title'] for p in by_id.values()], queries=online.get('queries',[]))
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(report['state'],'selected',len(by_id),'cited',len(cited))
        return int(not (report['state']=='success' and verified and named_cited and report['has_separate_review']))


if __name__=='__main__':
    raise SystemExit(main())
