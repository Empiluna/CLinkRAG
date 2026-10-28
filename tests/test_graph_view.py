import unittest
from debug_ui.graph_view import build_view


class GraphViewTests(unittest.TestCase):
    def fixture(self):
        graph={'graph_version':'a'*20,'entities':[{'id':'e','name':'retrieval'}],
               'passages':[{'id':'w'+str(i),'paper_id':'p'+str(i),'title':'Paper '+str(i),'text':'Source '+str(i)} for i in range(4)],
               'mentions':[{'entity_id':'e','passage_id':'w'+str(i),'paper_id':'p'+str(i),'mention':'retrieval'} for i in range(3)],
               'claims':[], 'associations':{'edges':[]}}
        out={'seeds':[graph['passages'][0]],'candidates':graph['passages'][:3],'entry_reasons':{}}
        events=[{'event':'start','id':'x','name':'retrieval'}, {'event':'end','id':'x','output':out}]
        result={'sources':[{'id':'p1','passage_id':'w1'}],'answer':'Evidence [0]','retrieved_passage_ids':['w0','w1','w2']}
        return graph,result,events

    def test_scope_dedup_and_citations_do_not_imply_causal_links(self):
        graph,result,events=self.fixture()
        view=build_view(graph,result,events)
        self.assertEqual({n['id'] for n in view['nodes']},{'p0','p1','p2'})
        self.assertEqual(len(view['edges']),3)
        self.assertTrue(all(e['type']=='shared' and not e['directed'] for e in view['edges']))
        self.assertTrue(next(n for n in view['nodes'] if n['id']=='p1')['cited'])

    def test_relation_witnesses_exclude_unretrieved_passages(self):
        graph,result,events=self.fixture()
        events[1]['output']['candidates']=graph['passages'][:1]
        result={'sources':[],'retrieved_passage_ids':['w0']}
        view=build_view(graph,result,events)
        self.assertEqual(len(view['nodes']),1)
        self.assertFalse(view['edges'])

    def test_online_citation_direction_and_isolated_paper_retained(self):
        papers=[{'paper':{'paperId':'a','title':'A'},'references':[{'paperId':'b','title':'B'}]},
                {'paperId':'c','title':'C'}]
        events=[{'event':'start','id':'x','kind':'retrieval'}, {'event':'end','id':'x','output':papers}]
        view=build_view({},None,events)
        self.assertEqual(len(view['nodes']),3)
        self.assertEqual([(e['source'],e['target'],e['type']) for e in view['edges']],[('a','b','citation')])
        self.assertFalse(view['has_entity_graph'])

    def test_raw_api_candidates_are_not_all_counted_as_admitted(self):
        events=[{'event':'start','id':'raw','kind':'http'},
                {'event':'end','id':'raw','output':{'body':{'data':[{'paperId':'a','title':'A'},{'paperId':'b','title':'B'}]}}},
                {'event':'start','id':'chosen','kind':'retrieval'},
                {'event':'end','id':'chosen','output':[{'paperId':'a','title':'A'}]}]
        view=build_view({},None,events)
        self.assertEqual(len(view['nodes']),2)
        self.assertEqual([n['id'] for n in view['nodes'] if n['retrieved']],['a'])

    def test_candidate_cross_paper_link_not_marked_as_used(self):
        graph,result,events=self.fixture()
        graph['claims']=[{'id':str(i),'paper_id':'p'+str(i),'source':'x','target':'e','quote':'original'} for i in range(2)]
        result['candidate_paths']=[{'id':'chain','claim_ids':['0','1'],'paper_ids':['p0','p1'],'state':'uncertain'}]
        view=build_view(graph,result,events)
        link=next(e for e in view['edges'] if e['type']=='path')
        self.assertFalse(link['selected'])
        self.assertEqual(link['state'],'uncertain')
        self.assertEqual(len(link['evidence']),2)


if __name__=='__main__':unittest.main()
