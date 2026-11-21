"""Evaluate realistic pasted-method requests on other attributed conference papers."""
import argparse
import hashlib
import json
from pathlib import Path
from statistics import mean
from unittest.mock import patch

if __package__:
    from .audit_method_ranking import ROOT, Ranker, historic, inference_settings, metrics, score_case
else:
    from audit_method_ranking import ROOT, Ranker, historic, inference_settings, metrics, score_case
from clinkrag import retrieval
from evaluation.benchmark_cs_ai import paired_interval

FIXTURE = ROOT/'evaluation/data/cross_paper_method_examples.json'
FROZEN = '6f066c9a897b395cf66e7bd9b0859b785ee7fd8ef230e9059e9a787c451c02b6'
FIXTURES = {
    'original': (FIXTURE, FROZEN),
    'confirmation': (ROOT/'evaluation/data/cross_paper_method_confirmation.json',
                     'df8b55d33796d178027698da3f66a3c8629183f88384d90484feface8bc37359'),
}


def sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def evaluate(device, dataset='original'):
    path, frozen = FIXTURES[dataset]
    text = path.read_text(encoding='utf-8')
    assert sha(text) == frozen
    fixture = json.loads(text)
    content = (ROOT/fixture['source']).read_text(encoding='utf-8')
    assert sha(content) == fixture['source_sha256_lf']
    docs = list(map(json.loads,content.splitlines()))
    group = fixture['pool']
    assert len(group) == len(set(group))
    assert not ({r['anchor'] for r in fixture['cases']} & set(group))
    if dataset == 'confirmation':
        original = json.loads(FIXTURE.read_text(encoding='utf-8'))
        earlier = set(original['pool']) | {r['anchor'] for r in original['cases']}
        assert earlier.isdisjoint(set(group) | {r['anchor'] for r in fixture['cases']})
    papers = sorted([{'paperId':docs[i]['paper_id'],'title':docs[i]['title'],'abstract':docs[i]['text']}
                     for i in group],key=lambda paper:paper['paperId'])
    old_rank = historic(fixture['baseline'])
    ranker = Ranker(device)
    rows = []
    for item in fixture['cases']:
        anchor = docs[item['anchor']]
        qid = 'method-'+str(item['anchor'])
        grades = {p['paperId']:0 for p in papers}
        for index, grade, reason in item['judgments']:
            assert index in group and grade in (1,2,3) and reason
            grades[docs[index]['paper_id']] = grade
        for index, reason in item['distractors']:
            assert index in group and grades[docs[index]['paper_id']]==0 and reason
        start, end = item.get('span', (0,len(anchor['text'])))
        assert 0 <= start < end <= len(anchor['text'])
        passage = anchor['text'][start:end].strip()
        assert len(passage)>300
        query = (item['request']+'\n\n' if item['request'] else '') + passage
        input_kind = ('bare-excerpt' if not item['request'] else
                      'request-with-excerpt' if 'span' in item else 'request-with-full-abstract')
        length = len(' '.join(query.split()))
        assert 300 < length <= 4000 and len(anchor['text'])>300
        case = dict(qid=qid, facet='independent-examples', question=query, papers=papers)
        semantic = score_case(ranker,case,device)
        plan = dict(topic_queries=[item['rewrite']],dimensions=[])
        old = old_rank(query, semantic, plan)
        # Observe execution of the real passage scorer as well as its public result.
        with patch.object(retrieval,'_long_question_lexical',wraps=retrieval._long_question_lexical) as probe:
            new = retrieval.fuse_rankings(query, semantic, plan)
        same = [(r['paperId'],r['fusion_score']) for r in old] == [(r['paperId'],r['fusion_score']) for r in new]
        if not probe.called and not same:
            raise AssertionError('Full-document rank or score changed for a pasted reference')
        results = {}
        for label, ranking in [('before',old),('after',new)]:
            ids = [r['paperId'] for r in ranking]
            assert len(set(ids)) == len(group) and anchor['paper_id'] not in ids
            results[label] = dict(qid=qid, **metrics(ranking, grades, 2),
                                  top10=ids[:10],positive_ranks={pid:ids.index(pid)+1 for pid in ids if grades[pid]>=2})
        rows.append(dict(qid=qid,label=item['label'],source_title=anchor['title'],source_url=anchor['url'],
                         intent=item['request'],input_sha256=sha(query),chars=length,
                         input_kind=input_kind,source_range=[start,end],
                         passage_scorer_called=probe.call_count==1, all_ranks_and_scores_equal_to_baseline=same,
                         relevant=sum(v>=2 for v in grades.values()),
                         **results))
    summary = {}
    for metric in ('Recall@10','nDCG@10','Hit@3'):
        prev = [row['before'] for row in rows]
        curr = [row['after'] for row in rows]
        summary[metric] = {'before':round(mean(r[metric] for r in prev),4),
                           'after':round(mean(r[metric] for r in curr),4),
                           **paired_interval(prev,curr,metric)}
    return {'baseline_commit':fixture['baseline'], 'frozen_fixture_sha256_lf':frozen,
            'source_sha256_lf':sha(content),'candidate_pool':len(group),
            'production_ranker_sha256_lf':sha((ROOT/'clinkrag/retrieval.py').read_text(encoding='utf-8')),
            'inference':inference_settings(device),'model_pairs':len(group)*len(rows),
            'activated':sum(r['passage_scorer_called'] for r in rows),
            'protocol':fixture['protocol'],
            'scope':'Project-authored sample and judgments, seven tasks. BGE scored the exact user input '
                    'against actual candidate abstracts. A fixed topical rewrite avoids planner variability. '
                    'This is a ranking-stage assessment; real web retrieval, model-generated rewrites and user '
                    'satisfaction are not measured. Sample intervals do not establish broader generalization.',
            'summary':summary,'cases':rows,
            'papers':{docs[i]['paper_id']:dict(row=i,title=docs[i]['title'],url=docs[i]['url']) for i in group}}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device',default='cuda:0')
    parser.add_argument('--dataset',choices=sorted(FIXTURES),default='original')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--without-reference-guard',action='store_true',
                        help='Replay the first-blind routing before recognizing pasted abstracts.')
    args=parser.parse_args()
    if args.without_reference_guard:
        with patch.object(retrieval,'_reference_needs_document',return_value=False):
            report=evaluate(args.device,args.dataset)
        report['variant']='before-reference-guard'
    else:
        report=evaluate(args.device,args.dataset)
    args.output.parent.mkdir(exist_ok=True,parents=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(report['activated'], 'of', len(report['cases']), 'triggered', json.dumps(report['summary']))
