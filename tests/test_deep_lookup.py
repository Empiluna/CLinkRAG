"""Exercise explicit-paper lookup, recovery and selection through the deep-research entry."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from test_online_retrieval import ROOT, FakeModel, FakeRanker, Recorder, paper, plan
from clinkrag.online import collect
from clinkrag.paper_ids import matches_reference, paper_references, without_references
from clinkrag.retrieval import fuse_rankings


class Reply:
    def __init__(self, payload, status=200):
        self.payload, self.status_code = payload, status

    def json(self):
        return copy.deepcopy(self.payload)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(str(self.status_code))


class DeepLookupTests(unittest.TestCase):
    def setUp(self):
        temporary_root = ROOT / 'results' / 'algorithm-test-temp'
        temporary_root.mkdir(parents=True, exist_ok=True)
        directory=tempfile.TemporaryDirectory(dir=temporary_root)
        self.addCleanup(directory.cleanup)
        self.folder=Path(directory.name)
        self.batches=[]
        self.queries=[]
        self.needle=dict(paper('named','Named method'),externalIds={'ArXiv':'1706.03762'})
        self.topic_paper=paper('topic','One comparison')
        self.response=Reply([self.needle])
        self.question='比较 arXiv:1706.03762 的设计和随后相关工作。'
        self.model=FakeModel(plan())
        self.fail_at_query=None

    def serve(self, method, url, **kw):
        if method=='POST':
            self.assertEqual(url,'https://api.semanticscholar.org/graph/v1/paper/batch')
            self.assertIsNone(kw['max_attempts'])
            self.assertIn('externalIds',kw['params']['fields'])
            self.batches.append(kw['json']['ids'])
            return self.response
        query=kw['params']['query']
        self.queries.append(query)
        if query==self.fail_at_query:
            self.fail_at_query=None
            raise RuntimeError('interrupted')
        return Reply({'data':[self.topic_paper]})

    def collect(self,limit=2):
        with patch('s2_transport.request',side_effect=self.serve):
            return collect(self.question,limit,{'S2_API_KEY':'fixture'},self.model,FakeRanker(),
                           Recorder(),self.folder,extra_queries=0)

    def test_explicit_references_are_checked_even_when_absent_from_keyword_results(self):
        result=self.collect()
        self.assertEqual(self.batches,[['ARXIV:1706.03762']])
        self.assertEqual({p['paperId'] for p in result['papers']},{'named','topic'})
        self.assertEqual(result['requested_references'],{'ARXIV:1706.03762':'named'})
        self.assertEqual(self.collect(),result)
        self.assertEqual(len(self.batches),1)

    def test_named_paper_still_requires_a_direct_original_quote(self):
        self.model.verdicts={'named':'unrelated'}
        result=self.collect()
        self.assertEqual([p['paperId'] for p in result['papers']],['topic'])
        self.assertEqual(result['assessments']['named']['relevance']['verdict'],'unrelated')

    def test_invalid_provider_identity_is_not_treated_as_the_named_paper(self):
        self.response=Reply([dict(self.needle,externalIds={'ArXiv':'2106.09685'})])
        result=self.collect()
        self.assertEqual(result['requested_references'],{'ARXIV:1706.03762':None})
        self.assertEqual([p['paperId'] for p in result['papers']],['topic'])

    def test_verified_keyword_hit_recovers_an_unresolved_batch_identity(self):
        self.response=Reply([None])
        self.topic_paper=self.needle
        result=self.collect()
        self.assertEqual(result['requested_references'],{'ARXIV:1706.03762':'named'})
        self.assertTrue(result['papers'][0]['ranking']['named_in_question'])

    def test_pointwise_scoring_reuses_unchanged_text_only(self):
        class PointwiseRanker:
            independent_pair_scores=True
            def __init__(self):
                self.sizes=[]
            def rank(self,q,items,text):
                self.sizes.append(len(items))
                return sorted([dict(p,score=len(text(p))) for p in items],key=lambda p:-p['score'])
        from test_online_retrieval import Transport
        p1,p2,p3=paper('first'),paper('second'),paper('last')
        transport=Transport({'Sobolev':[p1,p2], '嵌入定理':[p1], 'Sobolev direction 1':[p1,p2]})
        config=plan()
        fallback=config['dimensions'][0]['followup_query']
        transport.routes[fallback]=[p2,p3]
        ranker=PointwiseRanker()
        with patch('s2_transport.request',side_effect=transport.request):
            result=collect('Sobolev embedding',4,{'S2_API_KEY':'fixture'},FakeModel(config),ranker,
                           Recorder(),self.folder,dimension_sources=5,extra_queries=1)
        self.assertEqual(ranker.sizes,[2,1])
        self.assertEqual(result['ranking_policy']['semantic_pairs_scored_this_session'],3)
        self.assertEqual({p['paperId'] for p in result['papers']},{'first','second','last'})

    def test_long_question_still_supplies_lexical_evidence(self):
        question='Please compare the different approaches in detail. '*8+'Key issue: gradient checkpointing.'
        items=[dict(paper('general','General survey'),score=2),dict(paper('target','Gradient checkpointing'),score=1)]
        ranked=fuse_rankings(question,items,{'topic_queries':['unmatched snippet']})
        self.assertGreater(len(question),300)
        target=next(p for p in ranked if p['paperId']=='target')
        self.assertEqual(target['ranking']['lexical_rank'],1)

    def test_null_and_provider_rejection_continue_with_keyword_search(self):
        for response in (Reply([None]),Reply({},400)):
            with self.subTest(response=response.status_code):
                self.response=response
                result=self.collect()
                self.assertEqual([p['paperId'] for p in result['papers']],['topic'])
                (self.folder/'online-corpus.json').unlink()

    def test_partial_batch_is_retried_from_checkpoint(self):
        self.response=Reply([])
        with self.assertRaisesRegex(ValueError,'清单不完整'):
            self.collect()
        self.assertNotIn('ARXIV:1706.03762',json.loads((self.folder/'online-corpus.json').read_text(encoding='utf8')).get('requested_references',{}))
        self.response=Reply([self.needle])
        self.fail_at_query='Sobolev'
        with self.assertRaisesRegex(RuntimeError,'interrupted'):
            self.collect()
        self.collect()
        self.assertEqual(len(self.batches),2)
        self.assertEqual(self.model.planning_calls,1)

    def test_later_usable_abstract_fills_in_a_first_missing_one(self):
        self.question='文献 arXiv:1706.03762 的结果'
        self.response=Reply([dict(self.needle,abstract=None)])
        self.topic_paper=self.needle
        result=self.collect()
        self.assertEqual([p['paperId'] for p in result['papers']],['named'])
        self.assertEqual(result['papers'][0]['abstract'],self.needle['abstract'])

    def test_reference_variants_and_scope(self):
        text='比较 arXiv:1706.03762v4、https://arxiv.org/pdf/1706.03762.pdf 与 DOI:10.48550/arXiv.2106.09685。'
        self.assertEqual(paper_references(text),['ARXIV:1706.03762','ARXIV:2106.09685'])
        self.assertEqual(paper_references('见 https://arxiv.org/abs/math.GT/0309136v1'),['ARXIV:math.gt/0309136'])
        self.assertEqual(paper_references('参见(https://doi.org/10.1234/volume(1)).'),['DOI:10.1234/volume(1)'])
        self.assertEqual(paper_references('10.1234/abc;10.4321/def'),['DOI:10.1234/abc','DOI:10.4321/def'])
        self.assertEqual(paper_references('增长到 1706.03762 单位'),[])
        self.assertEqual(paper_references('1706.03762v3'),['ARXIV:1706.03762'])
        self.assertEqual(paper_references('记录 1706.03762v3',allow_bare_arxiv=True),['ARXIV:1706.03762'])
        self.assertFalse(paper_references('arXiv:2413.12345'))
        self.assertNotIn('10.1234',without_references('DOI:10.1234/source 引用'))
        self.assertTrue(matches_reference('DOI:10.18653/v1/n19-1423',{'externalIds':{'DOI':'10.18653/v1/N19-1423'}}))

    def test_planner_cannot_create_an_exact_reference_request(self):
        self.question='Which textual sources discuss Sobolev embeddings?'
        self.model.plan['topic_queries']=['arXiv:1706.03762']
        result=self.collect()
        self.assertFalse(self.batches)
        self.assertEqual([p['paperId'] for p in result['papers']],['topic'])


if __name__=='__main__':
    unittest.main()
