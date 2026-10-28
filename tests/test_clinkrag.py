import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from clinkrag.core import Config,association_stats,build_paths,compatible,locate,prepare_corpus
from clinkrag.index import verified_records,persist_sqlite
from clinkrag.pipeline import pack_context

class CLinkTests(unittest.TestCase):
    def test_cooccurrence_expands_retrieval_without_becoming_causal(self):
        from clinkrag.pipeline import retrieve
        class FixedRanker:
            def rank(self, question, records, text):
                return [dict(p, score=4-i) for i,p in enumerate(records)]
        graph={'passages':[{'id':w,'paper_id':w,'title':w,'text':w} for w in ['w1','w3','w2','w4']],
               'mentions':[{'passage_id':w,'entity_id':e} for w,e in [('w1','a'),('w3','a'),('w3','b'),('w2','b'),('w4','c')]],
               'claims':[], 'associations':{'edges':[{'source':'a','target':'b','eligible':True,'score':0.5}]}}
        included,reasons=retrieve('question',graph,FixedRanker(),Config(seeds=1,hops=1))
        excluded,_=retrieve('question',graph,FixedRanker(),Config(seeds=1,hops=1,associations=False))
        self.assertEqual({p['id'] for p in included},{'w1','w2','w3'})
        self.assertEqual({p['id'] for p in excluded},{'w1','w3'})
        self.assertTrue(any(r['type']=='co_occurs' for r in reasons['w2']))
        self.assertEqual(build_paths(graph['claims'],{},Config())[0],[])

    def test_no_overlap_and_source_offsets(self):
        text=('Retrieval noise can affect answers. '*50)+'\n\n'+('More evidence is needed. '*20)
        corpus=prepare_corpus([{'id':'p','text':text},{'id':'p','text':text}])
        self.assertEqual(len(corpus['papers']),1)
        for p in corpus['passages']:self.assertEqual(text[p['start']:p['end']],p['text'])
        for a,b in zip(corpus['passages'],corpus['passages'][1:]):self.assertLessEqual(a['end'],b['start'])

    def test_frequency_counts_presence_not_repeated_mentions(self):
        passages=[{'id':'w1','paper_id':'p1'},{'id':'w2','paper_id':'p2'},{'id':'w3','paper_id':'p2'}]
        mentions=[{'passage_id':'w1','entity_id':e} for e in ['a','a','a','b']]
        mentions += [{'passage_id':'w2','entity_id':e} for e in ['a','b']]
        stats=association_stats(passages,mentions,Config(min_windows=2))
        edge=stats['edges'][0]
        self.assertEqual((edge['ci'],edge['cj'],edge['cij'],edge['paper_count']),(2,2,2,2))
        self.assertTrue(edge['eligible'])
        self.assertEqual(edge['type'],'co_occurs');self.assertFalse(edge['directed'])

    def test_no_nan_when_pair_occurs_everywhere(self):
        stats=association_stats([{'id':'w','paper_id':'p'}],[{'passage_id':'w','entity_id':e} for e in ['a','b']],Config())
        self.assertEqual(stats['edges'][0]['score'],0)
        json.dumps(stats,allow_nan=False)

    def test_conditions_missing_never_means_compatible(self):
        self.assertEqual(compatible({}, {})['state'],'unknown')
        self.assertEqual(compatible({'task':'QA'}, {'task':'classification'})['state'],'conflict')

    def test_paths_preserve_direction_and_never_promote_cooccurrence(self):
        base={'verified':True,'conditions':{},'source_state':'present','target_state':'present'}
        claims=[dict(base,id='1',source='a',target='b',type='reported_causal',paper_id='p1',passage_id='w1'),
                dict(base,id='2',source='b',target='c',type='co_occurs',paper_id='p2',passage_id='w2')]
        paths,_=build_paths(claims,{'w1':1,'w2':1},Config())
        self.assertTrue(all(len(p['claim_ids'])==1 for p in paths))
        claims[1]['type']='reported_causal'
        paths,_=build_paths(claims,{'w1':1,'w2':1},Config())
        cross=[p for p in paths if len(p['paper_ids'])>1]
        self.assertEqual(len(cross),1);self.assertEqual(cross[0]['state'],'uncertain')
        claims[1]['source_state']='decreases'
        paths,rejected=build_paths(claims,{'w1':1,'w2':1},Config())
        self.assertFalse(any(len(p['paper_ids'])>1 for p in paths));self.assertTrue(rejected)

    def test_ungrounded_quote_and_reviewer_rejection_removed(self):
        corpus=prepare_corpus([{'id':'p','text':'Noise causes errors in this controlled experiment. More tests are needed.'}])
        passage=corpus['passages'][0];pid=passage['id']
        extraction={'entities':[{'mention':'Noise','canonical':'noise','type':'factor','passage_id':pid},
                                {'mention':'errors','canonical':'errors','type':'outcome','passage_id':pid}],
                    'claims':[{'source':'noise','source_type':'factor','target':'errors','target_type':'outcome',
                        'type':'reported_causal','passage_id':pid,'quote':'Noise always causes errors everywhere.'}]}
        review={'entities':[{'index':0,'accept':True},{'index':1,'accept':True}], 'claims':[{'index':0,'accept':True}]}
        self.assertFalse(verified_records(corpus,{pid},extraction,review)[2])
        extraction['claims'][0]['quote']='Noise causes errors in this controlled experiment.'
        self.assertEqual(len(verified_records(corpus,{pid},extraction,review)[2]),1)
        review['claims'][0]['accept']=False
        self.assertFalse(verified_records(corpus,{pid},extraction,review)[2])

    def test_budget_includes_metadata_and_preserves_full_passages(self):
        passages=[{'id':str(i),'paper_id':str(i),'title':'title','text':'Evidence content. '*30} for i in range(20)]
        packed=pack_context(passages,[],[],[],Config(context_tokens=500))
        self.assertLessEqual(packed['context_tokens'],500)
        self.assertGreater(len(packed['passages']),0)
        for item in packed['passages']:self.assertIn(item,passages)

    def test_corpus_version_changes_on_edit_or_deletion(self):
        a={'id':'a','text':'This is original scientific evidence. '*4}
        b={'id':'b','text':'This is different scientific evidence. '*4}
        self.assertNotEqual(prepare_corpus([a,b])['version'],prepare_corpus([a])['version'])
        modified=dict(a,text=a['text']+' Changed claim.')
        self.assertNotEqual(prepare_corpus([a])['version'],prepare_corpus([modified])['version'])

    def test_judge_misnumbering_not_confused_with_absent_evidence(self):
        from clinkrag.evaluate import audit_judge_record
        record={'claims':[{'supported':True,'source_index':1,'quote':'Noise can affect the result.'}],
                'criteria':[{'id':'c','met':True},{'id':'c','met':True}]}
        result=audit_judge_record(record,[{'text':'Noise can affect the result.'}], [{'id':'c'}])
        self.assertEqual(result['supported_claim_fraction'],1)
        self.assertEqual(result['judge_index_mismatches'],1)
        self.assertEqual(result['criteria_fraction'],1)

if __name__=='__main__':unittest.main()
