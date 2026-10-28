"""Workbench contract: lifecycle, persistence, trace integrity and local boundaries."""
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from debug_ui.server import Jobs, make_handler, validate_request
from debug_ui.tracing import Recorder


class DebugUITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_request_validation_rejects_unbounded_and_boolean_parameters(self):
        for data in [{'question': 'x'}, {'question': 'valid question', 'initial_papers': True},
                     {'question': 'valid question', 'max_tokens': 100000}, []]:
            with self.assertRaises(ValueError):
                validate_request(data)
        self.assertEqual(validate_request({'question': ' valid question '})['question'], 'valid question')
        self.assertEqual(validate_request({'question':'valid question','method':'clinkrag'})['method'],'clinkrag')
        with self.assertRaises(ValueError):
            validate_request({'question':'valid question','method':'shell'})

    def test_trace_nested_failure_is_persistent_and_secrets_are_redacted(self):
        recorder = Recorder(self.root/'events.jsonl', ['test-secret-value'])
        with self.assertRaisesRegex(RuntimeError, 'failure'):
            with recorder.step('parent', inputs={'api_key': 'anything', 'text': 'test-secret-value'}):
                with recorder.step('child'):
                    raise RuntimeError('failure test-secret-value')
        content = recorder.path.read_text(encoding='utf-8')
        self.assertNotIn('test-secret-value', content)
        self.assertNotIn('anything', content)
        events = [json.loads(line) for line in content.splitlines()]
        self.assertEqual(events[1]['parent'], events[0]['id'])
        self.assertEqual([e['status'] for e in events if e['event']=='end'], ['error','error'])
        self.assertEqual([e['seq'] for e in events], [1,2,3,4])

    def test_single_job_cancel_and_export_survive_reopen(self):
        jobs = Jobs(self.root)
        process = Mock()
        process.poll.return_value = None
        with patch('debug_ui.server.subprocess.Popen', return_value=process):
            run = jobs.create({'question': 'valid question'})
            with self.assertRaisesRegex(ValueError, '已有任务'):
                jobs.create({'question': 'second question'})
            recorder = Recorder(jobs.folder(run['id'])/'events.jsonl')
            with recorder.step('fixture', inputs={'query': 'persist me'}) as step:
                step['output'] = ['evidence']
            state = jobs.cancel(run['id'])
        self.assertEqual(state['status'], 'cancelled')
        process.terminate.assert_called_once()
        reopened = Jobs(self.root)
        self.assertEqual(len(reopened.events(run['id'])), 2)
        self.assertEqual(len(reopened.events(run['id'], after=1)), 1)
        self.assertEqual(reopened.state(run['id'])['status'], 'cancelled')

    def test_unexpected_worker_exit_is_not_reported_as_success(self):
        jobs = Jobs(self.root)
        process = Mock(returncode=7)
        process.poll.return_value = 7
        with patch('debug_ui.server.subprocess.Popen', return_value=process):
            run = jobs.create({'question': 'valid question'})
        self.assertEqual(run['status'], 'error')
        self.assertIn('7', run['error'])

    def test_repeated_submission_reuses_task_and_rejects_parameter_changes(self):
        jobs = Jobs(self.root)
        process = Mock()
        process.poll.return_value = None
        payload = {'question': 'valid question', 'method': 'clinkrag',
                   'client_request_id': '12345678-1234-1234-1234-123456789abc'}
        with patch('debug_ui.server.subprocess.Popen', return_value=process) as spawn:
            first = jobs.create(payload)
            second = jobs.create(payload)
            self.assertEqual(first['id'], second['id'])
            self.assertEqual(spawn.call_count, 1)
            with self.assertRaisesRegex(ValueError, '不同参数'):
                jobs.create({**payload, 'question': 'a changed question'})
        # Deduplication survives service restart and never silently restarts an interrupted job.
        reopened = Jobs(self.root)
        with patch('debug_ui.server.subprocess.Popen') as spawn:
            resumed = reopened.create(payload)
            self.assertEqual(resumed['id'], first['id'])
            self.assertEqual(resumed['status'], 'interrupted')
            spawn.assert_not_called()

    def test_request_id_validation(self):
        with self.assertRaises(ValueError):
            validate_request({'question':'valid question','client_request_id':'../other'})

    def test_incomplete_event_line_is_ignored_until_finished(self):
        jobs = Jobs(self.root)
        identity = 'a'*32
        folder = self.root/identity
        folder.mkdir()
        path = folder/'events.jsonl'
        path.write_text('{"seq":1}\n{"seq":', encoding='utf-8')
        self.assertEqual(jobs.events(identity), [{'seq': 1}])

    def test_http_requires_local_host_and_mutation_token(self):
        jobs = Jobs(self.root)
        server = ThreadingHTTPServer(('127.0.0.1',0), make_handler(jobs,'fixture-token'))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        try:
            with urllib.request.urlopen(base+'/') as response:
                self.assertIn('科学研究工作台', response.read().decode())
            for headers in [{'Host': 'attacker.invalid'}, {}]:
                request = urllib.request.Request(base+'/api/runs', data=b'{}', headers=headers)
                with self.assertRaises(urllib.error.HTTPError) as context:
                    urllib.request.urlopen(request)
                self.assertEqual(context.exception.code,403)
            request = urllib.request.Request(base+'/api/runs',data=b'{"question":"valid question"}',
                headers={'X-SciRAG-Token':'fixture-token','Origin':'https://attacker.invalid'})
            with self.assertRaises(urllib.error.HTTPError) as context:
                urllib.request.urlopen(request)
            self.assertEqual(context.exception.code,403)
            with urllib.request.urlopen(base+'/api/config') as response:
                config = json.load(response)
                self.assertNotIn('DEEPSEEK_API_KEY',config)
                self.assertNotIn('S2_API_KEY',config)
            with self.assertRaises(ValueError):
                jobs.folder('../config.local.yaml')
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == '__main__':
    unittest.main()
