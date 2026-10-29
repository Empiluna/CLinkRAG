"""Offline retrieval integration: mock network/model, exercise real checkpoints."""
from collections import Counter
from contextlib import contextmanager
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'longans'))
from clinkrag.online import collect, correction_query, review_budget, topic_queries, POLICY_VERSION
from clinkrag.retrieval import assessment_pool, fuse_rankings, lexical_scores, terms
from clinkrag.structured import StructuredOutputError


def paper(pid, subject='Sobolev embedding'):
    return {'paperId': pid, 'title': f'{subject}: source {pid}', 'year': 2020,
            'abstract': f'This source {pid} presents a rigorous account of {subject} and states the assumptions required for its conclusions.'}


def plan(kind='proof', mode='theoretical', directions=1):
    return {'question_type': kind, 'evidence_mode': mode,
            'evidence_needs': ['Precise theorem assumptions', 'Proof and counterexamples'],
            'subject_terms': ['Sobolev', '嵌入定理'], 'topic_queries': ['Sobolev', '嵌入定理'],
            'dimensions': [{'label': f'研究方向 {i}', 'query': f'Sobolev direction {i}',
                            'followup_query': f'Sobolev alternative {i}'} for i in range(1, directions + 1)]}


class Recorder:
    def __init__(self):
        self.events = []

    def clean(self, value):
        return copy.deepcopy(value)

    @contextmanager
    def step(self, name, kind, inputs):
        event = {'name': name, 'kind': kind, 'input': inputs}
        self.events.append(event)
        yield event


class FakeRanker:
    def __init__(self):
        self.calls = 0

    def rank(self, question, papers, text):
        self.calls += 1
        return [dict(p, score=float(len(papers)-i)) for i, p in enumerate(papers)]


class FakeModel:
    def __init__(self, research_plan, verdicts=None, corrections=None):
        self.plan = research_plan
        self.verdicts = verdicts or {}
        self.corrections = list(corrections or [])
        self.planning_calls = 0
        self.correction_calls = 0
        self.assessment_batches = []

    def json(self, prompt, **kwargs):
        if prompt.startswith('Plan literature retrieval'):
            self.planning_calls += 1
            return copy.deepcopy(self.plan)
        if prompt.startswith('Correct a literature search'):
            self.correction_calls += 1
            return {'query': self.corrections.pop(0) if self.corrections else ''}
        if prompt.startswith('Assess relevance and scope'):
            documents = json.loads(prompt.split('\nDocuments: ', 1)[1])
            self.assessment_batches.append([d['paperId'] for d in documents])
            items = []
            for document in documents:
                pid, quote = document['paperId'], document['text']
                verdict = self.verdicts.get(pid, 'direct')
                items.append({'paperId': pid,
                    'relevance': {'verdict': verdict, 'quote': quote, 'reason': 'Offline fixture judgment'},
                    'dimensions': [{'id': f'd{i}', 'quote': quote} for i in range(1, len(self.plan['dimensions'])+1)]
                                  if verdict == 'direct' else [],
                    'kind': 'theoretical', 'kind_quote': quote,
                    'contribution': {'type': 'theory', 'quote': quote}})
            return {'papers': items}
        raise AssertionError('Unexpected model call: ' + prompt[:120])


class FakeResponse:
    def __init__(self, papers):
        self.papers = papers

    def raise_for_status(self):
        pass

    def json(self):
        return {'data': copy.deepcopy(self.papers)}


class Transport:
    def __init__(self, routes, fail_once=None):
        self.routes = routes
        self.fail_once = set(fail_once or [])
        self.queries = []
        self.options = []

    def request(self, method, url, **kwargs):
        query = kwargs['params']['query']
        self.queries.append(query)
        self.options.append(kwargs)
        if query in self.fail_once:
            self.fail_once.remove(query)
            raise RuntimeError('Fixture interruption during search')
        if query not in self.routes:
            raise AssertionError('Unexpected query: ' + query)
        return FakeResponse(self.routes[query])


class OnlineRetrievalTests(unittest.TestCase):
    def setUp(self):
        # Keep fixture outputs separate from real research and OS sandbox temp ACLs.
        temporary_root = ROOT / 'results' / 'algorithm-test-temp'
        temporary_root.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix='online-', dir=temporary_root)
        self.addCleanup(self.temporary.cleanup)
        self.job = Path(self.temporary.name)
        self.recorder = Recorder()
        self.ranker = FakeRanker()

    def collect(self, model, transport, **kwargs):
        with patch('s2_transport.request', side_effect=transport.request):
            return collect('Sobolev 嵌入定理如何证明？', kwargs.pop('limit', 3),
                           {'S2_API_KEY': 'fixture-only'}, model, self.ranker, self.recorder, self.job,
                           **kwargs)

    def saved(self):
        return json.loads((self.job / 'online-corpus.json').read_text(encoding='utf-8'))

    def test_plan_query_ranks_and_completed_checkpoint_are_preserved(self):
        research_plan = plan()
        a, b = paper('a'), paper('b')
        transport = Transport({'Sobolev': [b, a], '嵌入定理': [a], 'Sobolev direction 1': [a, b]})
        model = FakeModel(research_plan)
        result = self.collect(model, transport, extra_queries=0)
        self.assertEqual(result['plan']['question_type'], 'proof')
        self.assertEqual(result['plan']['evidence_mode'], 'theoretical')
        self.assertEqual(result['plan']['subject_terms'], research_plan['subject_terms'])
        self.assertEqual(result['plan']['evidence_needs'], research_plan['evidence_needs'])
        self.assertEqual(result['policy_version'], POLICY_VERSION)
        indexed = {p['paperId']: p for p in self.saved()['candidates']}
        self.assertEqual(indexed['a']['query_ranks'], {'Sobolev': 2, '嵌入定理': 1, 'Sobolev direction 1': 1})
        self.assertEqual(result['query_dimensions']['Sobolev direction 1'], 'd1')
        self.assertTrue(all(p['ranking']['method'] == 'weighted-rrf' for p in result['papers']))
        self.assertTrue(all(o['max_attempts'] is None for o in transport.options))
        counts = (len(transport.queries), self.ranker.calls, len(model.assessment_batches))
        repeated = self.collect(model, transport, extra_queries=0)
        self.assertEqual(repeated, self.saved())
        self.assertEqual(counts, (len(transport.queries), self.ranker.calls, len(model.assessment_batches)))
        self.assertEqual(model.planning_calls, 1)

    def test_interrupted_initial_search_reuses_successful_query_and_plan(self):
        model = FakeModel(plan())
        transport = Transport({'Sobolev': [paper('a')], '嵌入定理': [paper('b')],
                               'Sobolev direction 1': [paper('a')]}, fail_once=['嵌入定理'])
        with self.assertRaisesRegex(RuntimeError, 'Fixture interruption'):
            self.collect(model, transport, extra_queries=0)
        self.assertEqual(self.saved()['queries'], ['Sobolev'])
        self.assertEqual(model.assessment_batches, [])
        result = self.collect(model, transport, extra_queries=0)
        self.assertEqual(Counter(transport.queries), {'Sobolev': 1, '嵌入定理': 2, 'Sobolev direction 1': 1})
        self.assertEqual(model.planning_calls, 1)
        self.assertEqual({p['paperId'] for p in result['papers']}, {'a', 'b'})

    def test_interrupted_correction_reuses_query_and_grounded_assessments(self):
        initial = [paper('good'), paper('bad-1'), paper('bad-2')]
        model = FakeModel(plan(), {'bad-1': 'unrelated', 'bad-2': 'uncertain'}, corrections=['Sobolev compact embeddings'])
        transport = Transport({'Sobolev': initial, '嵌入定理': initial, 'Sobolev direction 1': initial,
                               'Sobolev compact embeddings': [paper('new-good')]}, fail_once=['Sobolev compact embeddings'])
        with self.assertRaisesRegex(RuntimeError, 'Fixture interruption'):
            self.collect(model, transport, extra_queries=1, dimension_sources=2)
        saved = self.saved()
        self.assertEqual(saved['pending_supplement'], {'query': 'Sobolev compact embeddings', 'dimension': 'd1'})
        self.assertEqual(saved['supplemented_dimensions'], ['d1'])
        self.assertEqual(len(saved['assessments']), 3)
        result = self.collect(model, transport, extra_queries=1, dimension_sources=2)
        counts = Counter(pid for batch in model.assessment_batches for pid in batch)
        self.assertEqual(counts, {'good': 1, 'bad-1': 1, 'bad-2': 1, 'new-good': 1})
        self.assertEqual(Counter(transport.queries)['Sobolev compact embeddings'], 2)
        self.assertEqual(model.correction_calls, 1)
        self.assertEqual(model.planning_calls, 1)
        self.assertNotIn('pending_supplement', result)
        self.assertEqual({p['paperId'] for p in result['papers']}, {'good', 'new-good'})

    def test_resume_retries_unavailable_assessment_but_reuses_successful_review(self):
        class TransientModel(FakeModel):
            unavailable_once = True

            def json(self, prompt, **kwargs):
                if prompt.startswith('Assess relevance and scope') and self.unavailable_once:
                    documents = json.loads(prompt.split('\nDocuments: ', 1)[1])
                    if any(d['paperId'] == 'retry' for d in documents):
                        # Fail the batch and then its single-paper recovery, just once.
                        if len(documents) == 1:
                            self.unavailable_once = False
                        raise StructuredOutputError('Fixture temporary malformed assessment')
                return super().json(prompt, **kwargs)

        initial = [paper('unrelated'), paper('retry')]
        model = TransientModel(plan(), {'unrelated': 'unrelated'})
        transport = Transport({'Sobolev': initial, '嵌入定理': initial, 'Sobolev direction 1': initial})
        with self.assertRaisesRegex(ValueError, '结构化输出无效'):
            self.collect(model, transport, extra_queries=0)
        before = self.saved()
        self.assertEqual(before['assessments']['retry']['status'], 'unavailable')
        self.assertEqual(before['assessments']['unrelated']['relevance']['verdict'], 'unrelated')
        self.assertFalse(before.get('complete'))

        result = self.collect(model, transport, extra_queries=0)
        reviewed = Counter(pid for batch in model.assessment_batches for pid in batch)
        self.assertEqual(reviewed, {'unrelated': 1, 'retry': 1})
        self.assertEqual(result['assessments']['unrelated'], before['assessments']['unrelated'])
        self.assertEqual(result['assessments']['retry']['relevance']['verdict'], 'direct')
        self.assertNotIn('status', result['assessments']['retry'])
        self.assertEqual([p['paperId'] for p in result['papers']], ['retry'])
        self.assertEqual(Counter(transport.queries), {'Sobolev': 1, '嵌入定理': 1, 'Sobolev direction 1': 1})
        self.assertEqual(model.planning_calls, 1)

    def test_review_pool_is_bounded_even_with_many_independent_directions(self):
        research_plan = plan('overview', 'mixed', directions=4)
        queries = research_plan['topic_queries'] + [d['query'] for d in research_plan['dimensions']]
        routes = {q: [paper(f'{group}-{i}') for i in range(30)] for group, q in enumerate(queries)}
        model, transport = FakeModel(research_plan), Transport(routes)
        observed = []
        def bounded_pool(*args, **kwargs):
            result = assessment_pool(*args, **kwargs)
            observed.append((args[2], len(result)))
            return result
        with patch('clinkrag.online.assessment_pool', side_effect=bounded_pool):
            result = self.collect(model, transport, limit=5, extra_queries=0)
        self.assertEqual(len(result['candidates']), 180)
        self.assertEqual(result['ranking_policy']['review_pool_limit'], 24)
        self.assertEqual(len(result['assessments']), 24)
        self.assertEqual(observed, [(24, 24)])
        self.assertTrue(all(len(batch) <= 6 for batch in model.assessment_batches))
        self.assertLessEqual(len(result['papers']), 5)

    def test_poor_result_correction_stays_bounded_and_never_relaxes_relevance(self):
        research_plan = plan('overview', 'mixed', directions=4)
        queries = research_plan['topic_queries'] + [d['query'] for d in research_plan['dimensions']]
        routes = {q: [paper('bad', 'smoking cessation advertising')] for q in queries}
        routes.update({'Sobolev counterexamples': [paper('uncertain')], 'Sobolev function spaces': [paper('also-bad')]})
        model = FakeModel(research_plan, {'bad': 'unrelated', 'uncertain': 'uncertain', 'also-bad': 'unrelated'},
                          ['Sobolev counterexamples', 'Sobolev function spaces'])
        transport = Transport(routes)
        observed = []
        def bounded_pool(*args, **kwargs):
            result = assessment_pool(*args, **kwargs)
            observed.append((args[2], len(result)))
            return result
        with patch('clinkrag.online.assessment_pool', side_effect=bounded_pool):
            with self.assertRaisesRegex(ValueError, '没有合适的回答来源'):
                self.collect(model, transport, extra_queries=2)
        saved = self.saved()
        self.assertEqual(model.correction_calls, 2)
        self.assertEqual(len(transport.queries), len(queries)+2)
        self.assertEqual(len(saved['supplemented_dimensions']), 2)
        self.assertEqual(saved['papers'], [])
        self.assertFalse(any(p['selected'] for p in saved['candidates']))
        self.assertTrue(all(count <= budget for budget, count in observed))
        self.assertTrue(all(a['relevance']['verdict'] != 'direct' for a in saved['assessments'].values()))

    def test_empty_rewrites_cannot_spend_more_model_calls_than_extra_query_budget(self):
        research_plan = plan('overview', 'mixed', directions=4)
        for direction in research_plan['dimensions']:
            direction['followup_query'] = direction['query']
        queries = research_plan['topic_queries'] + [d['query'] for d in research_plan['dimensions']]
        model = FakeModel(research_plan, {'bad': 'unrelated'})
        transport = Transport({q: [paper('bad')] for q in queries})
        with self.assertRaisesRegex(ValueError, '没有合适的回答来源'):
            self.collect(model, transport, extra_queries=1)
        self.assertLessEqual(model.correction_calls, 1)
        self.assertEqual(len(transport.queries), len(queries))
        # Reopening an unsuccessful run cannot reset and spend the same budget.
        with self.assertRaisesRegex(ValueError, '没有合适的回答来源'):
            self.collect(model, transport, extra_queries=1)
        self.assertLessEqual(model.correction_calls, 1)
        self.assertEqual(len(transport.queries), len(queries))

    def test_query_aliases_are_searched_once_and_doi_metadata_is_requested(self):
        research_plan = plan()
        research_plan['topic_queries'] = ['Self-RAG', ' self rag ']
        research_plan['dimensions'][0]['query'] = 'SELF–RAG'
        model = FakeModel(research_plan)
        document = paper('a', 'Self-RAG')
        document['externalIds'] = {'DOI': '10.1000/fixture'}
        transport = Transport({'Self RAG': [document]})
        result = self.collect(model, transport, extra_queries=0)
        self.assertEqual(transport.queries, ['Self RAG'])
        self.assertEqual(result['candidates'][0]['query_ranks'], {'Self RAG': 1})
        self.assertEqual(result['candidates'][0]['externalIds']['DOI'], '10.1000/fixture')
        self.assertIn('externalIds', transport.options[0]['params']['fields'])
        # The same alias must also retain its direction's reserved review slot.
        ranked = [dict(paper(str(i)), queries=[]) for i in range(4)]
        ranked.append(dict(paper('alias'), queries=['Self RAG']))
        direction_plan = {'topic_queries': [], 'dimensions': [{'id': 'd1', 'query': 'SELF–RAG'}]}
        self.assertIn('alias', [p['paperId'] for p in assessment_pool(ranked, direction_plan, 3)])

    def test_old_policy_reuses_downloads_but_replans_and_rechecks_stale_approval(self):
        source = dict(paper('old'), queries=['Sobolev'], selected=True, assessment={'relevance': {'verdict': 'direct'}})
        old = {'question': 'Sobolev 嵌入定理如何证明？', 'limit': 3, 'policy_version': 'question-relevance-v2',
               'queries': ['Sobolev'], 'candidates': [source], 'papers': [source], 'complete': True,
               'assessments': {'old': source['assessment']}, 'supplemented_dimensions': ['d1'],
               'pending_supplement': {'query': 'Old inappropriate query', 'dimension': 'd1'},
               'plan': {'question_type': 'comparison', 'origin': 'user',
                        'dimensions': [{'id': 'd1', 'label': '用户指定方向', 'query': 'Old query'}]}}
        (self.job / 'online-corpus.json').write_text(json.dumps(old, ensure_ascii=False), encoding='utf-8')
        research_plan = plan()
        research_plan['dimensions'][0]['label'] = '用户指定方向'
        model = FakeModel(research_plan, {'old': 'unrelated'})
        transport = Transport({'嵌入定理': [], 'Sobolev direction 1': []})
        with self.assertRaisesRegex(ValueError, '没有合适的回答来源'):
            self.collect(model, transport, extra_queries=0)
        saved = self.saved()
        self.assertEqual(transport.queries, ['嵌入定理', 'Sobolev direction 1'])
        self.assertEqual(model.planning_calls, 1)
        self.assertEqual(model.assessment_batches, [['old']])
        self.assertEqual(saved['plan']['origin'], 'user')
        self.assertEqual(saved['plan']['dimensions'][0]['label'], '用户指定方向')
        self.assertEqual(saved['plan']['evidence_mode'], 'theoretical')
        self.assertEqual(saved['papers'], [])
        self.assertEqual(saved['assessments']['old']['relevance']['verdict'], 'unrelated')
        self.assertNotIn('pending_supplement', saved)

    def test_original_language_and_single_technical_queries_are_valid(self):
        self.assertEqual(topic_queries(['拓扑', 'Sobolev', ' sobolev ', '']), ['拓扑', 'Sobolev'])
        self.assertEqual(topic_queries('not a list'), [])
        self.assertIn('拓扑', terms('拓扑学'))
        self.assertIn('h1', terms('Sobolev H1'))
        self.assertEqual(review_budget({'question_type': 'proof', 'dimensions': [{}, {}]}, 3), 16)
        self.assertEqual(review_budget({'question_type': 'overview', 'dimensions': [{}, {}, {}, {}]}, 3), 24)
        self.assertEqual(review_budget({'question_type': 'proof', 'dimensions': [{}]}, 30), 60)

    def test_duplicate_correction_is_rejected_without_requesting_it_again(self):
        model = FakeModel(plan(), corrections=['  SOBOLEV   embedding  '])
        self.assertEqual(correction_query({'question': 'Sobolev embedding'}, {'label': 'Proof'}, [], {},
                                         ['Sobolev embedding'], model), '')

    def test_lexical_signal_supports_cjk_and_preserves_raw_reranker_scores(self):
        documents = ['量子纠缠与拓扑绝缘体', '文艺复兴时期的艺术史', '函数空间的嵌入定理与Sobolev条件']
        scores = lexical_scores('Sobolev 嵌入定理', documents)
        self.assertGreater(scores[2], scores[0])
        self.assertGreater(scores[2], scores[1])
        rows = [dict(paper(str(i)), abstract=text, score=50.0-i,
                     query_ranks={'Sobolev': i+1}, queries=['Sobolev']) for i, text in enumerate(documents)]
        normalized_plan = plan()
        normalized_plan['dimensions'] = [dict(d, id=f'd{i}') for i, d in enumerate(normalized_plan['dimensions'], 1)]
        output = fuse_rankings('Sobolev 嵌入定理', rows, normalized_plan)
        self.assertEqual({p['paperId']: p['score'] for p in output}, {str(i): 50.0-i for i in range(3)})
        self.assertEqual(next(p for p in output if p['paperId']=='2')['ranking']['lexical_rank'], 1)


if __name__ == '__main__':
    unittest.main()
