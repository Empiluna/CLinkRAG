"""Regression tests use controlled fixtures, never real credentials or API calls."""
import copy
import json
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'longans'))
import pipe
import web_search
from run import process_input_data
from llms import get_model


class ScriptedModel:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def chat(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        return next(self.responses)


class StartupTests(unittest.TestCase):
    def sample(self):
        return process_input_data([json.loads((ROOT / 'examples/sample.jsonl').read_text(encoding='utf-8'))])[0]

    def test_early_termination_pipeline(self):
        model = ScriptedModel(['[Response_Start]Outline[Response_End]',
            '[Response_Start]A fixture answer about SciRAG [0].[Response_End]', '[end]terminate'])
        with patch.object(pipe, 'get_model', return_value=model):
            answer, cost, refs = pipe.pipeline().run(self.sample(), 'deepseek-flash')
        self.assertIn('fixture answer', answer)
        self.assertEqual(len(refs), 1)
        self.assertEqual(len(model.calls), 3)

    def test_full_pipeline_with_and_without_symbolic_expansion(self):
        for expanded in (True, False):
            with self.subTest(expanded=expanded):
                responses = ['Outline', 'Initial fixture answer [0].', '(1) Supporting evidence']
                if expanded:
                    responses += ['{"papers": []}', '{"relationships": []}',
                        '{"final_selection": [{"paper_index": 1, "rank": 1, "justification": "Fixture evidence"}]}']
                responses += ['Additional fixture evidence [1].', 'Merged fixture answer [1].',
                              '[terminate]', 'Attributed fixture answer [0].']
                model = ScriptedModel(responses)
                papers = [{'paper': {'paperId': 'fixture:1', 'title': 'Fixture paper',
                                     'abstract': 'Controlled test evidence.'},
                           'references': [], 'citations': []}]
                runner = pipe.pipeline()
                runner._reranker = SimpleNamespace(compute_score=Mock(return_value=0.75))
                with patch.object(pipe, 'get_model', return_value=model), patch.object(
                        pipe, 'search_snippet_via_query_w_citation_expansion',
                        return_value=(copy.deepcopy(papers), expanded, 0)) as search:
                    answer, cost, refs = runner.run(self.sample(), 'deepseek-flash', max_thread=1)
                self.assertEqual(answer, 'Attributed fixture answer [0].')
                self.assertEqual(len(refs), 2)
                self.assertEqual(search.call_args.kwargs['model'], 'deepseek-flash')
                self.assertEqual(len(model.calls), len(responses))
                runner._reranker.compute_score.assert_called_once()

    def test_invalid_symbolic_json_fails_explicitly(self):
        model = ScriptedModel(['{}', '{}', 'invalid'])
        with patch.object(pipe, 'get_model', return_value=model), self.assertRaisesRegex(ValueError, 'invalid JSON'):
            pipe.pipeline().symbolic_reason_rerank([{'text': 'evidence'}], 'path', 'query', 'deepseek-flash')

    def test_query_aliases_and_missing_context(self):
        sample = self.sample()
        self.assertEqual(sample['query'], sample['input'])
        with self.assertRaisesRegex(ValueError, 'nonempty ctxs'):
            process_input_data([{'question': 'Question?'}])

    def test_deepseek_adapter_json_and_transport(self):
        response = SimpleNamespace(choices=[SimpleNamespace(
            message=SimpleNamespace(content='{"ok":true}'), finish_reason='stop')])
        sdk = Mock()
        sdk.chat.completions.create.return_value = response
        with patch.dict(os.environ, {'DEEPSEEK_API_KEY': 'test-only-not-a-secret'}), patch(
                'llms.openai_model.OpenAI', return_value=sdk) as factory:
            model = get_model('deepseek-flash')
            self.assertEqual(json.loads(model.chat('Return ok', json_mode=True))['ok'], True)
        self.assertIn('api.deepseek.com', factory.call_args.kwargs['base_url'])
        request = sdk.chat.completions.create.call_args.kwargs
        self.assertEqual(request['model'], 'deepseek-flash')
        self.assertEqual(request['extra_body']['thinking']['type'], 'disabled')
        self.assertEqual(request['response_format']['type'], 'json_object')
        self.assertIn('JSON', request['messages'][0]['content'])
        self.assertEqual(factory.call_args.kwargs['max_retries'], 2)

    def test_snippet_search_uses_requested_model(self):
        snippet = Mock(status_code=200)
        snippet.json.return_value = {'data': [{'paper': {'corpusId': 123}, 'snippet': {'text': 'Evidence'}}]}
        batch = Mock(status_code=200)
        batch.json.return_value = [{'paperId': 'fixture:123', 'title': 'Fixture', 'abstract': 'Evidence', 'authors': []}]
        model = ScriptedModel(['[end]terminate'])
        with patch.object(web_search, 'S2_API_KEY', 'test-only'), patch.object(web_search.requests, 'get', return_value=snippet), patch.object(
                web_search.requests, 'post', return_value=batch), patch.object(web_search.time, 'sleep'), patch.object(
                web_search, 'get_model', return_value=model) as factory:
            papers, expanded, cost = web_search.search_snippet_via_query_w_citation_expansion('query', model='deepseek-flash')
        self.assertFalse(expanded)
        self.assertEqual(papers[0]['paper']['paperId'], 'fixture:123')
        factory.assert_called_once_with('deepseek-flash')

    def test_retrieval_failure_does_not_synthesize_without_evidence(self):
        response = Mock(status_code=403, text='fixture access denied')
        with patch.object(web_search, 'S2_API_KEY', 'test-only'), patch.object(web_search.requests, 'get', return_value=response), patch.object(
                web_search.time, 'sleep'), self.assertRaisesRegex(RuntimeError, 'retrieval failed'):
            web_search.search_snippet_via_query_w_citation_expansion('query')

    def test_unknown_tariff_does_not_crash(self):
        self.assertEqual(pipe.calculate_openai_api_cost(50, 50, 'deepseek-flash'), 0.0)


if __name__ == '__main__':
    unittest.main()
