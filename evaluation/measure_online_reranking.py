"""Replay the deep collection path with real BGE scores and fixed provider/model responses."""
import argparse
import json
import os
from pathlib import Path
import statistics
import sys
import tempfile
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'longans'), str(ROOT / 'tests')]
os.environ.setdefault('HF_HOME', str(ROOT / '.cache' / 'huggingface'))

from clinkrag.online import collect
from clinkrag.runtime import Ranker
from test_online_retrieval import FakeModel, Recorder, Transport


class ReplayModel(FakeModel):
    """Return verifiable, short excerpts so the real review gate can run."""
    def json(self, prompt, **kwargs):
        if prompt.startswith('Assess relevance and scope'):
            header, payload = prompt.split('\nDocuments: ', 1)
            documents = json.loads(payload)
            for doc in documents:
                doc['text'] = doc['text'][:200]
            prompt = header + '\nDocuments: ' + json.dumps(documents)
        return super().json(prompt, **kwargs)


def run(device, repetitions):
    import torch
    raw = json.loads((ROOT / 'evaluation/data/corpus.json').read_text(encoding='utf-8'))['papers']
    papers = [dict(paperId=p['id'], title=p['title'], abstract=p['text']) for p in raw]
    question = 'How do adaptive retrieval and evidence verification improve retrieval-augmented generation?'
    plan = {'question_type': 'comparison', 'topic_queries': ['retrieval augmented generation'],
            'dimensions': [{'label':'adaptive retrieval','query':'adaptive retrieval',
                            'followup_query':'selective retrieval'},
                           {'label':'verification','query':'evidence verification',
                            'followup_query':'verifying attributed answers'}]}
    routes = {'retrieval augmented generation':papers[:16], 'adaptive retrieval':papers[:12],
              'evidence verification':papers[4:16], 'selective retrieval':papers[14:22],
              'verifying attributed answers':papers[20:]}
    ranker = Ranker(device)
    # Warm the exact model/device before timing either collection path.
    ranker.rank(question, [papers[0]], text=lambda p:p['abstract'])
    reports = {}
    modes = ('full','incremental') if getattr(ranker, 'independent_pair_scores', False) else ('full',)
    for iteration in range(repetitions):
        for mode in (modes if not iteration % 2 else reversed(modes)):
            ranker.independent_pair_scores = mode == 'incremental'
            measured = {'pairs':0, 'calls':0, 'model_seconds':0.0}
            def measure(pairs, *args, **kwargs):
                start = time.perf_counter()
                result = compute(pairs, *args, **kwargs)
                measured['pairs'] += len(pairs)
                measured['calls'] += 1
                measured['model_seconds'] += time.perf_counter()-start
                return result
            model, transport = ReplayModel(plan), Transport(routes)
            compute = ranker.model.compute_score
            with tempfile.TemporaryDirectory() as directory, patch.object(ranker.model, 'compute_score', side_effect=measure), patch('s2_transport.request', side_effect=transport.request):
                start=time.perf_counter()
                output=collect(question,8,{'S2_API_KEY':'fixture'},model,ranker,Recorder(),Path(directory),
                               dimension_sources=9,extra_queries=2)
                measured['collect_seconds'] = time.perf_counter()-start
            if len(output['candidates']) != 28 or len(transport.queries) != 5:
                raise AssertionError('Fixture did not exercise all three rerank passes.')
            measured.update(selected=[p['paperId'] for p in output['papers']],
                            ranked=sorted((p['paperId'] for p in output['candidates']),
                                          key={p['paperId']:-p['score'] for p in output['candidates']}.__getitem__),
                            scores={p['paperId']:p['score'] for p in output['candidates']},
                            http_calls=len(transport.queries), candidates=len(output['candidates']))
            reports.setdefault(mode, []).append(measured)
    result = {'fixture':'28 frozen S2 passages from evaluation/data/corpus.json, 16 then +6 and +6. Five HTTP responses and planner/assessor are deterministic fixtures, BGE inference and selection are real.',
              'device':torch.cuda.get_device_name(device) if device.startswith('cuda') else device,
              'model':ranker.model.model.config._name_or_path.split('snapshots')[0].split('models--')[-1].strip('/\\').replace('--','/'),
              'warmup':'one excluded pair before measurement; mode order alternates', 'repetitions':repetitions,'modes':{}}
    for mode,runs in reports.items():
        result['modes'][mode] = {'pairs':[r['pairs'] for r in runs],
            'model_seconds':[round(r['model_seconds'],4) for r in runs],
            'collect_seconds':[round(r['collect_seconds'],4) for r in runs],
            'median_model_seconds':round(statistics.median(r['model_seconds'] for r in runs),4),
            'median_collect_seconds':round(statistics.median(r['collect_seconds'] for r in runs),4),
            'http_calls':runs[0]['http_calls'],'candidates':runs[0]['candidates'],'selected':runs[0]['selected']}
    if len(reports) == 2:
        pairs = zip(reports['full'], reports['incremental'])
        pairs = list(pairs)
        result['same_selected_and_order']=all(a['selected']==b['selected'] for a,b in pairs)
        result['same_semantic_order']=all(a['ranked']==b['ranked'] for a,b in pairs)
        result['max_raw_score_difference']=max(abs(x-b['scores'][k]) for a,b in pairs for k,x in a['scores'].items())
    return result


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device',default='cuda:0')
    parser.add_argument('--repetitions',type=int,default=3)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.repetitions<1:parser.error('repetitions must be positive')
    report=json.dumps(run(args.device,args.repetitions),indent=2,ensure_ascii=False)
    if args.output:args.output.write_text(report+'\n',encoding='utf-8')
    print(report)
