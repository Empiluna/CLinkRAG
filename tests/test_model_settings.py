"""Configuration writes use temporary files; no user's config or remote API is touched."""
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from debug_ui.server import Jobs, make_handler
from debug_ui.model_settings import SettingsStore, validate, public_values


class ModelSettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.path = self.root / 'config.yaml'
        self.path.write_text(yaml.safe_dump({'MODEL_NAME': 'deepseek-test',
            'DEEPSEEK_API_KEY': 'private-original', 'OPENAI_API_KEY': 'private-compatible',
            'S2_API_KEY': 'private-search', 'OPENAI_BASE_URL': None,
            'custom_field': {'keep': True}}), encoding='utf-8')
        self.store = SettingsStore(self.path, lambda: yaml.safe_load(self.path.read_text(encoding='utf-8')))

    def tearDown(self):
        self.temp.cleanup()

    def payload(self):
        view = self.store.view()
        return {'revision': view['revision'], 'values': view['values'], 'secrets': {}}

    def test_read_redacts_keys_and_normalizes_legacy_null(self):
        view = self.store.view()
        self.assertNotIn('private-', json.dumps(view))
        self.assertTrue(view['credentials']['DEEPSEEK_API_KEY'])
        self.assertEqual(view['values']['LLM_PROVIDER'], 'deepseek')
        self.assertEqual(view['values']['OPENAI_BASE_URL'], 'https://api.openai.com/v1')
        validate(view['values'])

    def test_save_preserves_blank_keys_and_unknown_settings(self):
        payload = self.payload()
        payload['values'].update(LLM_PROVIDER='openai_compatible', MODEL_NAME='custom-model',
            RERANKER_MODEL='org/custom-reranker', RERANKER_BATCH_SIZE=7)
        payload['secrets'] = {'DEEPSEEK_API_KEY': '', 'S2_API_KEY': ' '}
        result = self.store.save(payload)
        config = yaml.safe_load(self.path.read_text())
        self.assertEqual(config['DEEPSEEK_API_KEY'], 'private-original')
        self.assertEqual(config['S2_API_KEY'], 'private-search')
        self.assertEqual(config['custom_field'], {'keep': True})
        self.assertEqual(result['values']['RERANKER_BATCH_SIZE'], 7)
        self.assertNotIn('private-', json.dumps(result))
        self.assertEqual(list(self.root.glob('.settings-*')), [])

    def test_replaces_only_submitted_key(self):
        payload = self.payload()
        payload['secrets'] = {'OPENAI_API_KEY': 'new-secret'}
        result = self.store.save(payload)
        data = yaml.safe_load(self.path.read_text())
        self.assertEqual(data['OPENAI_API_KEY'], 'new-secret')
        self.assertEqual(data['DEEPSEEK_API_KEY'], 'private-original')
        self.assertNotIn('new-secret', json.dumps(result))

    def test_native_claude_save_isolated_key_and_reload(self):
        payload = self.payload()
        payload['values'].update(LLM_PROVIDER='anthropic', MODEL_NAME='claude-sonnet-5-5')
        payload['secrets'] = {'ANTHROPIC_API_KEY': 'claude-private'}
        saved = self.store.save(payload)
        self.assertTrue(saved['llm_configured'])
        self.assertTrue(saved['credentials']['ANTHROPIC_API_KEY'])
        self.assertNotIn('claude-private', json.dumps(saved))
        self.assertEqual(self.store.view()['values']['LLM_PROVIDER'], 'anthropic')
        self.assertEqual(yaml.safe_load(self.path.read_text())['OPENAI_API_KEY'], 'private-compatible')

    def test_stale_revision_cannot_overwrite_another_editor(self):
        payload = self.payload()
        original = self.path.read_text()
        self.path.write_text(original + '\n# external edit\n')
        with self.assertRaisesRegex(ValueError, '重新加载'):
            self.store.save(payload)
        self.assertIn('# external edit', self.path.read_text())

    def test_invalid_values_do_not_change_file(self):
        original = self.path.read_bytes()
        for key, value in [('RERANKER_DEVICE', 'gpu'), ('RERANKER_BATCH_SIZE', True),
                ('RERANKER_MAX_LENGTH', 99999), ('REQUEST_TIMEOUT', 0),
                ('OPENAI_BASE_URL', 'https://api.test/v1?api_key=secret'),
                ('OPENAI_BASE_URL', 'https://user:secret@api.test'),
                ('OPENAI_BASE_URL', 'file:///tmp/file'), ('LLM_PROVIDER', 'unknown'),
                ('RERANKER_OFFLINE', 'false'), ('MODEL_NAME', ' '), ('MODEL_NAME', ['invalid'])]:
            with self.subTest(key=key, value=value):
                payload = self.payload();payload['values'][key] = value
                with self.assertRaises(ValueError):
                    self.store.save(payload)
                self.assertEqual(self.path.read_bytes(), original)

    def test_environment_override_rejected_without_losing_key(self):
        with patch.dict(os.environ, {'MODEL_NAME': 'fixed-model'}):
            payload = self.payload();payload['values']['MODEL_NAME'] = 'new-model'
            with self.assertRaisesRegex(ValueError, '环境变量'):
                self.store.save(payload)
        self.assertIn('private-original', self.path.read_text())

    def test_failed_replace_keeps_original_and_removes_temp(self):
        original = self.path.read_bytes()
        with patch('debug_ui.model_settings.os.replace', side_effect=OSError('fixture')):
            with self.assertRaises(OSError):
                self.store.save(self.payload())
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(list(self.root.glob('.settings-*')), [])

    def test_provider_is_independent_of_model_name(self):
        import llms
        with patch('llms.load_settings', return_value={'LLM_PROVIDER': 'openai_compatible'}), patch('llms.chatgpt') as compatible, patch('llms.DeepSeek') as deep:
            llms.get_model('deepseek-via-gateway')
            compatible.assert_called_once_with(model='deepseek-via-gateway')
            deep.assert_not_called()
        with patch('llms.load_settings', return_value={'LLM_PROVIDER': 'deepseek'}), patch('llms.DeepSeek') as deep:
            llms.get_model('custom-model')
            deep.assert_called_once_with(model='custom-model')

    def test_transport_receives_endpoint_timeout_retries_and_omits_vendor_option(self):
        from llms.openai_model import chatgpt
        config = {'LLM_PROVIDER': 'openai_compatible', 'OPENAI_API_KEY': 'fixture',
                  'OPENAI_BASE_URL': 'http://127.0.0.1:1234/v1', 'REQUEST_TIMEOUT': 31, 'MAX_RETRIES': 4}
        with patch('llms.openai_model.load_settings', return_value=config), patch('llms.openai_model.OpenAI') as client:
            response = client.return_value.chat.completions.create.return_value
            response.choices = [Mock(message=Mock(content='answer'), finish_reason='stop')]
            model = chatgpt('deepseek-custom')
            self.assertEqual(model.chat('question', json_mode=True), 'answer')
            kwargs = client.call_args.kwargs
            self.assertEqual((kwargs['base_url'], kwargs['timeout'], kwargs['max_retries']), ('http://127.0.0.1:1234/v1', 31, 4))
            self.assertNotIn('extra_body', client.return_value.chat.completions.create.call_args.kwargs)

    def test_both_pipelines_share_reranker_options(self):
        from llms.reranking import options, score_options
        from clinkrag.runtime import Ranker
        cfg = {'RERANKER_MODEL': 'org/custom', 'RERANKER_DEVICE': 'cpu', 'RERANKER_FP16': True,
               'RERANKER_BATCH_SIZE': 2, 'RERANKER_MAX_LENGTH': 768}
        with patch('llms.reranking.load_settings', return_value=cfg):
            self.assertFalse(options()['fp16'])
            self.assertEqual(score_options(), {'batch_size': 2, 'max_length': 768})
            scorer = Mock();scorer.compute_score.return_value = [.2, .8]
            with patch('llms.reranking.create_reranker', return_value=scorer):
                ranked = Ranker('cpu').rank('q', [{'text':'a'}, {'text':'b'}])
            scorer.compute_score.assert_called_once_with([['q','a'],['q','b']], batch_size=2, max_length=768)
            self.assertEqual(ranked[0]['text'], 'b')
            import pipe
            self.assertEqual(pipe.score_options(), score_options())
            self.assertIs(pipe.create_reranker, __import__('llms.reranking', fromlist=['create_reranker']).create_reranker)

    def test_offline_reranker_resolves_cache_and_disables_custom_code(self):
        from llms.reranking import create_reranker
        fake = Mock()
        cfg = {'RERANKER_MODEL':'org/custom','RERANKER_DEVICE':'cpu','RERANKER_OFFLINE':True}
        with patch('llms.reranking.load_settings', return_value=cfg), patch.dict(sys.modules, {'FlagEmbedding':fake}), patch('huggingface_hub.snapshot_download', return_value=str(self.root)) as cache, patch.dict(os.environ, {}, clear=False):
            create_reranker()
            cache.assert_called_once_with('org/custom', local_files_only=True)
            fake.FlagReranker.assert_called_once_with(str(self.root), use_fp16=False, devices='cpu', trust_remote_code=False)

    def test_settings_http_auth_save_and_active_run_guard(self):
        jobs = Jobs(self.root / 'runs')
        server = ThreadingHTTPServer(('127.0.0.1',0), make_handler(jobs,'test-token',self.store))
        thread = threading.Thread(target=server.serve_forever, daemon=True);thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        def post(payload, headers):
            return urlopen(Request(base+'/api/settings', data=json.dumps(payload).encode(), headers=headers))
        try:
            with urlopen(base+'/api/settings') as response:
                self.assertNotIn('private-', response.read().decode())
            for headers in ({}, {'X-SciRAG-Token':'test-token','Origin':'https://other.invalid'}):
                with self.assertRaises(HTTPError) as failure:
                    post(self.payload(),headers)
                self.assertEqual(failure.exception.code,403)
            payload = self.payload();payload['values']['MODEL_NAME'] = 'saved-model'
            with post(payload, {'X-SciRAG-Token':'test-token'}) as response:
                self.assertEqual(json.load(response)['values']['MODEL_NAME'], 'saved-model')
            with patch('debug_ui.server.subprocess.Popen', return_value=Mock(poll=Mock(return_value=None))):
                jobs.create({'question':'a valid question'})
            with self.assertRaises(HTTPError) as failure:
                post(self.payload(), {'X-SciRAG-Token':'test-token'})
            self.assertEqual(failure.exception.code,400)
            self.assertIn('研究正在运行', failure.exception.read().decode())
        finally:
            server.shutdown();server.server_close();thread.join()


if __name__ == '__main__':
    unittest.main()
