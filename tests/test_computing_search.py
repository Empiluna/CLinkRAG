"""Production source selection and bounded remote-result reuse."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import unittest
from unittest.mock import patch

from debug_ui import literature


class CrossrefReuseTests(unittest.TestCase):
    def setUp(self):
        self.cache=patch.object(literature,'_crossref_cache',literature.OrderedDict())
        self.cache.start()
        self.addCleanup(self.cache.stop)

    def test_same_remote_pool_shared_without_mutating_returned_metadata(self):
        entered, release=Event(),Event()
        def fetch(question,count):
            entered.set()
            if not release.wait(3):
                raise RuntimeError('test stalled')
            return [{'doi':question,'authors':['Ada']}]
        with patch.object(literature,'_fetch_crossref',side_effect=fetch) as remote, ThreadPoolExecutor(2) as workers:
            first=workers.submit(literature.crossref_papers,'graph   models',1)
            self.assertTrue(entered.wait(3))
            second=workers.submit(literature.crossref_papers,'graph models',3)
            release.set()
            first.result()[0]['authors'].clear()
            self.assertEqual(second.result()[0]['authors'],['Ada'])
            remote.assert_called_once_with('graph models',15)

    def test_expiry_different_pool_and_transient_failures(self):
        with patch.object(literature,'_fetch_crossref',side_effect=[
                [], OSError('unavailable'),[{'doi':'a'}],[{'doi':'b'}],[{'doi':'c'}]]) as fetch:
            with patch.object(literature,'monotonic',return_value=42):
                self.assertEqual(literature.crossref_papers('trees',2),[])
                with self.assertRaises(OSError):
                    literature.crossref_papers('trees',2)
                self.assertEqual(literature.crossref_papers('trees',2)[0]['doi'],'a')
                self.assertEqual(literature.crossref_papers('trees',2)[0]['doi'],'a')
                self.assertEqual(literature.crossref_papers('trees',10)[0]['doi'],'b')
            with patch.object(literature,'monotonic',return_value=345):
                self.assertEqual(literature.crossref_papers('trees',2)[0]['doi'],'c')
            self.assertEqual(fetch.call_count,5)
