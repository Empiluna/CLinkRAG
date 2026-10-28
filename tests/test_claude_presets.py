"""Native Claude and named provider contracts, entirely offline."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'longans'))
from debug_ui.model_settings import public_values, validate
from debug_ui.model_presets import PRESETS
from llms.anthropic_model import Claude
from llms.settings import configured_key


class ClaudePresetTests(unittest.TestCase):
    def client(self, **config):
        settings = {'ANTHROPIC_API_KEY':'fixture-secret', 'REQUEST_TIMEOUT':25, 'MAX_RETRIES':1, **config}
        with patch('llms.anthropic_model.load_settings', return_value=settings):
            return Claude('claude-sonnet-5-5')

    def response(self, text='answer', status=200, stop='end_turn'):
        result=Mock(status_code=status)
        result.json.return_value={'content':[{'type':'text','text':text}], 'stop_reason':stop,
                                  'usage':{'input_tokens':8,'output_tokens':2}}
        return result

    def test_native_endpoint_headers_system_and_sampling(self):
        response=self.response()
        with patch('llms.anthropic_model.requests.post',return_value=response) as post:
            model=self.client();self.assertEqual(model.chat('question',system_msg='system',temperature=0,max_tokens=200),'answer')
        args=post.call_args
        self.assertEqual(args.args[0],'https://api.anthropic.com/v1/messages')
        self.assertEqual(args.kwargs['headers']['x-api-key'],'fixture-secret')
        self.assertEqual(args.kwargs['headers']['anthropic-version'],'2023-06-01')
        self.assertFalse(args.kwargs['allow_redirects'])
        self.assertEqual(args.kwargs['timeout'],25)
        self.assertEqual(args.kwargs['json'],{'model':'claude-sonnet-5-5','system':'system','messages':[{'role':'user','content':'question'}],'max_tokens':200})
        self.assertEqual(model.last_usage,{'input_tokens':8,'output_tokens':2})
        response.close.assert_called_once()

    def test_native_base_url_with_v1_is_not_duplicated(self):
        self.assertEqual(self.client(ANTHROPIC_BASE_URL='https://gateway.test/anthropic/v1/').url,'https://gateway.test/anthropic/v1/messages')

    def test_json_response_and_fences_are_parsed_without_thinking_blocks(self):
        response=self.response('```json\n{"query":"scientific evidence"}\n```')
        response.json.return_value['content'].insert(0,{'type':'thinking','thinking':'not answer content'})
        with patch('llms.anthropic_model.requests.post',return_value=response) as post:
            output=self.client().chat('q',json_mode=True)
        self.assertEqual(json.loads(output),{'query':'scientific evidence'})
        self.assertIn('JSON object',post.call_args.kwargs['json']['system'])
        self.assertNotIn('response_format',post.call_args.kwargs['json'])

    def test_invalid_truncated_or_refused_json_fails_explicitly(self):
        for text,stop in [('not json','end_turn'),('[]','end_turn'),('{"x":','max_tokens'),('refusal','refusal'),('','end_turn')]:
            with self.subTest(text=text),patch('llms.anthropic_model.requests.post',return_value=self.response(text,stop=stop)):
                with self.assertRaises(RuntimeError):self.client().chat('q',json_mode=True)

    def test_retry_is_bounded_and_auth_errors_do_not_echo_body(self):
        with patch('llms.anthropic_model.requests.post',side_effect=[self.response(status=429),self.response()]) as post,patch('llms.anthropic_model.time.sleep') as sleep:
            self.assertEqual(self.client().chat('q'),'answer');self.assertEqual(post.call_count,2);sleep.assert_called_once()
        bad=self.response(status=401);bad.text='fixture-secret echoed by server'
        with patch('llms.anthropic_model.requests.post',return_value=bad) as post:
            with self.assertRaisesRegex(RuntimeError,'401') as error:self.client().chat('q')
            self.assertNotIn('fixture-secret',str(error.exception));self.assertEqual(post.call_count,1)
        with patch('llms.anthropic_model.requests.post',return_value=self.response(status=503)) as post,patch('llms.anthropic_model.time.sleep'):
            with self.assertRaisesRegex(RuntimeError,'503'):self.client().chat('q')
            self.assertEqual(post.call_count,2)

    def test_claude_never_uses_another_providers_key(self):
        settings={'LLM_PROVIDER':'anthropic','OPENAI_API_KEY':'other-key','DEEPSEEK_API_KEY':'other-key'}
        self.assertIsNone(configured_key(settings))
        with patch('llms.anthropic_model.load_settings',return_value=settings):
            with self.assertRaisesRegex(ValueError,'Claude'):Claude()
        import llms
        with patch('llms.load_settings',return_value=settings),patch('llms.Claude') as native,patch('llms.chatgpt') as other:
            llms.get_model('claude-sonnet-5-5');native.assert_called_once();other.assert_not_called()

    def test_named_presets_have_valid_config_and_documentation(self):
        for item in PRESETS:
            values=public_values({'MODEL_NAME':'custom','LLM_PROVIDER':item['id']})
            if item.get('base_url'):
                values[item['url_key']]=item['base_url'];values['MODEL_NAME']=item['models'][0]['id']
                self.assertTrue(item['docs'].startswith('https://'))
            validate(values)
        self.assertEqual({item['id'] for item in PRESETS},{'anthropic','deepseek','openai','qwen','openai_compatible'})

    def test_openai_modern_model_uses_appropriate_token_parameters(self):
        from llms.openai_model import chatgpt
        with patch('llms.openai_model.load_settings',return_value={'LLM_PROVIDER':'openai','OPENAI_API_KEY':'fixture'}),patch('llms.openai_model.OpenAI') as client:
            client.return_value.chat.completions.create.return_value.choices=[Mock(message=Mock(content='answer'),finish_reason='stop')]
            chatgpt('gpt-5.4-mini').chat('q',max_tokens=300)
            kwargs=client.return_value.chat.completions.create.call_args.kwargs
            self.assertEqual(kwargs['max_completion_tokens'],300);self.assertEqual(kwargs['reasoning_effort'],'none')
            for key in ('max_tokens','temperature','top_p','presence_penalty'):self.assertNotIn(key,kwargs)

    def test_qwen_uses_its_own_key_endpoint_and_non_thinking_mode(self):
        import llms
        config={'LLM_PROVIDER':'qwen','QWEN_API_KEY':'qwen-only','QWEN_BASE_URL':'https://qwen.test/v1','OPENAI_API_KEY':'unrelated'}
        with patch('llms.load_settings',return_value=config),patch('llms.openai_model.load_settings',return_value=config),patch('llms.openai_model.OpenAI') as client:
            client.return_value.chat.completions.create.return_value.choices=[Mock(message=Mock(content='answer'),finish_reason='stop')]
            llms.get_model('qwen-plus').chat('q')
            self.assertEqual(client.call_args.kwargs['api_key'],'qwen-only')
            self.assertEqual(client.call_args.kwargs['base_url'],'https://qwen.test/v1')
            self.assertEqual(client.return_value.chat.completions.create.call_args.kwargs['extra_body'],{'enable_thinking':False})

    def test_online_instrumentation_uses_shared_reranker_factory(self):
        from debug_ui.tracing import Recorder,instrument
        names=['run','gen_outline','initial_result','initial_critic','gap_critic','additional_references_expansion',
               'symbolic_reason_rerank','additional_result','bottom_up_aggregate','reflective_refine','insert_attributions_posthoc_paragraph_all']
        pipeline=type('Pipeline',(),{name:lambda *args,**kwargs:None for name in names})
        scorer=Mock();scorer.model.device='cpu';scorer.compute_score.return_value=[.5]
        factory=Mock(return_value=scorer)
        pipe=SimpleNamespace(pipeline=pipeline,get_model=Mock(),create_reranker=factory)
        search=SimpleNamespace(search_snippet_via_query_w_citation_expansion=lambda *a,**k:None)
        with tempfile.TemporaryDirectory() as directory,patch('requests.sessions.Session.send'):
            recorder=Recorder(Path(directory)/'events.jsonl')
            instrument(recorder,pipe,search)
            self.assertEqual(pipe.create_reranker().compute_score([['q','paper']],batch_size=2),[.5])
            factory.assert_called_once();scorer.compute_score.assert_called_once_with([['q','paper']],batch_size=2)
            self.assertIn('paper',recorder.path.read_text(encoding='utf-8'))


if __name__=='__main__':unittest.main()
