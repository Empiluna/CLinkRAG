"""Resume and permanent-deletion contracts, with isolated data and fake workers."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from debug_ui.server import BadRequest, Jobs, MissingRun


class RunLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.jobs = Jobs(self.root)
        self.request = {
            'question': 'An isolated research lifecycle question',
            'method': 'clinkrag_online',
            'client_request_id': '12345678-1234-1234-1234-123456789abc',
        }

    def tearDown(self):
        self.temp.cleanup()

    def create_run(self):
        worker = Mock()
        worker.poll.return_value = None
        with patch('debug_ui.server.subprocess.Popen', return_value=worker):
            run = self.jobs.create(self.request)
        return run, worker

    def test_resume_reuses_record_and_checkpoint_and_is_idempotent(self):
        run, worker = self.create_run()
        folder = self.jobs.folder(run['id'])
        checkpoint = {'query': 'cached query', 'papers': [{'paperId': 'fixture'}]}
        self.jobs.write(folder / 'online-corpus.json', checkpoint)
        events = '{"seq":1,"event":"start","id":"saved","name":"search"}\n'
        (folder / 'events.jsonl').write_text(events, encoding='utf-8')
        self.jobs.cancel(run['id'])
        worker.poll.return_value = 0
        resumed_worker = Mock()
        resumed_worker.poll.return_value = None
        with patch('debug_ui.server.subprocess.Popen', return_value=resumed_worker) as spawn:
            resumed = self.jobs.resume(run['id'])
            repeated = self.jobs.resume(run['id'])
        self.assertEqual(resumed['id'], run['id'])
        self.assertEqual(repeated['status'], 'running')
        spawn.assert_called_once()
        self.assertEqual(spawn.call_args.args[0][-1], '--resume')
        self.assertEqual(self.jobs.read(folder / 'online-corpus.json'), checkpoint)
        self.assertEqual((folder / 'events.jsonl').read_text(encoding='utf-8'), events)
        self.assertEqual(len(self.jobs.read(folder / 'resume-history.json')), 1)

    def test_resume_rejects_a_second_active_research(self):
        run, worker = self.create_run()
        self.jobs.cancel(run['id'])
        worker.poll.return_value = 0
        self.request = {**self.request, 'question': 'Another isolated research question',
                        'client_request_id': '22345678-1234-1234-1234-123456789abc'}
        other, _ = self.create_run()
        with patch('debug_ui.server.subprocess.Popen') as spawn:
            with self.assertRaisesRegex(BadRequest, '已有研究进程'):
                self.jobs.resume(run['id'])
            spawn.assert_not_called()
        self.assertEqual(self.jobs.state(other['id'])['status'], 'running')

    def test_permanent_delete_stops_worker_and_prevents_old_submission_recreation(self):
        run, worker = self.create_run()
        folder = self.jobs.folder(run['id'])
        self.jobs.write(folder / 'result.json', {'answer': 'fixture-only result'})
        worker.wait.side_effect = lambda **_: setattr(worker.poll, 'return_value', 0)
        result = self.jobs.delete(run['id'])
        worker.terminate.assert_called_once()
        worker.wait.assert_called_once_with(timeout=10)
        self.assertTrue(result['permanent'])
        self.assertFalse(folder.exists())
        self.assertEqual(self.jobs.listing(), [])
        with self.assertRaises(MissingRun):
            self.jobs.state(run['id'])
        self.assertEqual(self.jobs.delete(run['id']), result)
        reopened = Jobs(self.root)
        with patch('debug_ui.server.subprocess.Popen') as spawn:
            with self.assertRaisesRegex(BadRequest, '永久删除'):
                reopened.create(self.request)
            spawn.assert_not_called()
        receipt = json.dumps(reopened.read(self.root / '.deleted-receipts.json'))
        self.assertNotIn(self.request['question'], receipt)
        self.assertNotIn(self.request['client_request_id'], receipt)


if __name__ == '__main__':
    unittest.main()
