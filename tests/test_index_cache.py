"""An extraction cache must match the actual source passage identities."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from clinkrag.core import Config
from clinkrag.index import build_index


class FakeModel:
    name='offline-index-fixture'
    def __init__(self):
        self.calls=[]

    def json(self,prompt,**kwargs):
        self.calls.append(prompt)
        if prompt.startswith('Extract scientific concepts'):
            passages=json.loads(prompt.rsplit('Passages: ',1)[1])
            return {'entities':[{'mention':'archive','canonical':'archive','type':'concept',
                                 'definition':'A collection of original records',
                                 'passage_id':passages[0]['id']}], 'claims':[]}
        if prompt.startswith('Check extracted entities'):
            return {'entities':[{'index':0,'accept':True,'reason':'Present in the source'}], 'claims':[]}
        raise AssertionError('Unexpected model call')


class IndexCacheTests(unittest.TestCase):
    def paper(self,pid):
        return {'paperId':pid,'title':'Archival evidence',
                'text':'The archive contains original letters and institutional records used for historical interpretation.'}

    def test_identical_text_under_different_paper_ids_uses_its_own_passages(self):
        with tempfile.TemporaryDirectory() as cache:
            model=FakeModel()
            first=build_index([self.paper('source-a')],model,cache)
            second=build_index([self.paper('source-b')],model,cache)
            self.assertTrue(first['entities'])
            self.assertTrue(second['entities'])
            self.assertNotEqual(first['passages'][0]['id'],second['passages'][0]['id'])
            self.assertEqual(second['mentions'][0]['passage_id'],second['passages'][0]['id'])
            self.assertEqual(len(model.calls),4)

    def test_identical_input_reuses_graph_and_per_paper_extraction(self):
        with tempfile.TemporaryDirectory() as cache:
            model=FakeModel();papers=[self.paper('source-a')]
            first=build_index(papers,model,cache)
            same=build_index(papers,model,cache)
            self.assertEqual(same,first)
            self.assertEqual(len(model.calls),2)
            # A graph-only association setting changes the graph key, but the
            # unchanged source passages should still reuse their extraction.
            changed=build_index(papers,model,cache,config=Config(tau=9))
            self.assertNotEqual(first['graph_version'],changed['graph_version'])
            self.assertEqual(changed['entities'],first['entities'])
            self.assertEqual(len(model.calls),2)


if __name__=='__main__':unittest.main()
