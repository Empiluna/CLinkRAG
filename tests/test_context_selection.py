"""Offline cross-discipline fixtures for evidence packing and source provenance."""
import json
from pathlib import Path
import re
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from clinkrag.core import Config
from clinkrag.pipeline import generate,pack_context,retrieve
from clinkrag.runtime import token_count


def passage(pid,text,paper=None):
    return {'id':pid,'paper_id':paper or pid,'title':'Source '+pid,'text':text}


def research_for(passages,anchors=None,kind='theoretical'):
    anchors=anchors or {}
    return {'plan':{'question_type':'proof','evidence_mode':'theoretical',
                    'evidence_needs':['Assumptions and stated theorem'],
                    'dimensions':[{'id':'d1','label':'Main result'},{'id':'d2','label':'Boundary conditions'}]},
            'papers':[{'paperId':p['paper_id'],'assessment':{
                'kind':kind,'kind_quote':anchors.get(p['id'],''),
                'relevance':{'verdict':'direct','quote':anchors.get(p['id'],'')},
                'dimensions':[{'id':'d1','quote':anchors[p['id']]}] if p['id'] in anchors else []}}
                for p in passages]}


class FixedRanker:
    def rank(self,question,records,text):
        return [dict(p,score=10-i) for i,p in enumerate(records)]


class ContextSelectionTests(unittest.TestCase):
    def test_seed_budget_and_best_match_survive_irrelevant_dimensions(self):
        texts=[passage('theorem','For every finite abelian group the decomposition exists.'),
               passage('second','The uniqueness proof depends on finite generation.'),
               passage('weak','A broad survey mentions a similar classification label.')]
        research=research_for(texts,{'weak':texts[-1]['text']})
        graph={'passages':texts,'mentions':[],'claims':[],'associations':{'edges':[]}}
        candidates,reasons=retrieve('Finite abelian group decomposition',graph,FixedRanker(),
                                    Config(seeds=2,hops=0),research=research)
        self.assertEqual([p['id'] for p in candidates],['theorem','second'])
        self.assertEqual(len(reasons),2)

    def test_one_paper_does_not_crowd_out_independent_sources(self):
        p1=passage('a1','The historical interpretation concerns letters from 1850. '*25,'a')
        p2=passage('a2','The same edition describes related letters from 1851. '*25,'a')
        p3=passage('b1','A separate archive records the institutional response. '*25,'b')
        budget=token_count(json.dumps({'sources':[],'paths':[],'conflicts':[]}))+550
        packed=pack_context([p1,p2,p3],[],[],[],Config(context_tokens=budget))
        self.assertEqual([p['paper_id'] for p in packed['passages'][:2]],['a','b'])
        self.assertLessEqual(packed['context_tokens'],budget)

    def test_chinese_long_abstract_preserves_late_anchor_and_exact_offsets(self):
        anchor='本文依据地方档案和私人书信解释十九世纪教育制度的变化。'
        text='已有研究讨论若干相关历史背景。'*130+anchor+'这些材料仅来自两座城市。'+'附录说明不同档案的整理过程。'*120
        source=passage('history',text)
        source.update(start=80,end=80+len(text))
        research=research_for([source],{'history':anchor},kind='documentary')
        packed=pack_context([source],[],[],[],Config(context_tokens=800),research)
        retained=packed['passages'][0];span=retained['excerpt']
        self.assertIn(anchor,retained['text'])
        self.assertIn('这些材料仅来自两座城市。',retained['text'])
        self.assertEqual(text[span['start']:span['end']],retained['text'])
        self.assertEqual(retained['start'],80+span['start'])
        self.assertLessEqual(packed['context_tokens'],800)
        context=json.loads(packed['context'])
        self.assertEqual(context['sources'][0]['reported_evidence_kind'],'documentary')
        self.assertEqual(context['dimension_source_counts']['d1'],1)

    def test_unanchored_giant_single_sentence_is_not_fabricated_into_claim(self):
        source=passage('long','algebraic '*2000)
        with self.assertRaisesRegex(ValueError,'original evidence'):
            pack_context([source],[],[],[],Config(context_tokens=200))

    def test_short_chinese_anchored_span_can_rescue_oversized_sentence(self):
        anchor='制度变化受到地方协商影响'
        text='这是很长的背景材料'*250+anchor+'这是原句其余部分'*250
        source=passage('chinese',text)
        packed=pack_context([source],[],[],[],Config(context_tokens=400),research_for([source],{'chinese':anchor}))
        self.assertEqual(packed['passages'][0]['text'],anchor)
        self.assertIn('excerpt',packed['passages'][0])

    def test_unexcerptable_long_source_does_not_bypass_fair_share(self):
        long=passage('long','indivisible '*350)
        alternatives=[passage(str(i),'This separate source records a concrete historical finding. '*20) for i in range(3)]
        packed=pack_context([long]+alternatives,[],[],[],Config(context_tokens=1000))
        self.assertEqual({p['paper_id'] for p in packed['passages']},{'0','1','2'})
        self.assertLessEqual(packed['context_tokens'],1000)

    def test_large_paths_never_displace_question_evidence(self):
        sources=[passage(str(i),'A controlled measurement reports the following effect. '*10) for i in range(4)]
        claims=[{'id':'c1','passage_id':'0','paper_id':'0','quote':sources[0]['text'],
                 'source':'A','target':'B','type':'reported_causal','conditions':{'task':'large '*1000}},
                {'id':'c2','passage_id':'1','paper_id':'1','quote':sources[1]['text'],
                 'source':'B','target':'C','type':'reported_causal','conditions':{}}]
        path={'id':'chain','state':'uncertain','paper_ids':['0','1'],'passage_ids':['0','1'],
              'claim_ids':['c1','c2'],'checks':[]}
        config=Config(context_tokens=1500)
        baseline=pack_context(sources,[],claims,[],config)
        actual=pack_context(sources,[path],claims,[],config)
        self.assertEqual(actual['passages'],baseline['passages'])
        self.assertFalse(actual['paths'])
        self.assertLessEqual(actual['context_tokens'],1500)

    def test_path_metadata_requires_its_quote_inside_context(self):
        sources=[passage('a','The observed association is specific to the recorded setting.'),
                 passage('b','An independent measurement uses a distinct setting.')]
        claims=[{'id':'c','passage_id':'a','paper_id':'a','quote':'This quotation was not supplied.',
                 'source':'A','target':'B','type':'reported_causal','conditions':{}}]
        path={'id':'chain','state':'uncertain','paper_ids':['a','b'],'passage_ids':['a','b'],
              'claim_ids':['c'],'checks':[]}
        packed=pack_context(sources,[path],claims,[],Config(context_tokens=1800))
        self.assertFalse(packed['paths'])

    def test_whole_small_passages_are_unchanged(self):
        sources=[passage(str(i),'A mathematical statement with explicitly stated assumptions. '*10) for i in range(3)]
        packed=pack_context(sources,[],[],[],Config(context_tokens=900))
        for source in packed['passages']:
            self.assertIn(source,sources)
            self.assertNotIn('excerpt',source)

    def test_excerpt_does_not_export_unseen_contribution_or_scope(self):
        anchor='The method finds a feasible solution under the stated sparsity assumption.'
        missing='All measurements used the city transport dataset recorded in 2012.'
        text=anchor+' The guarantee applies to sparse inputs only. '+('Additional mathematical notation is defined separately. '*250)+missing
        source=passage('method',text)
        research=research_for([source],{'method':anchor},kind='methodological')
        assessment=research['papers'][0]['assessment']
        assessment['contribution']={'type':'method','quote':anchor}
        assessment['population']={'value':'City transport dataset','quote':missing}
        assessment['period']={'value':'2012','quote':missing}
        packed=pack_context([source],[],[],[],Config(context_tokens=650),research)
        actual=json.loads(packed['context'])['sources'][0]
        self.assertEqual(actual['contribution']['type'],'method')
        self.assertEqual(actual['scope']['population'],'unknown')
        self.assertEqual(actual['scope']['period'],'unknown')
        self.assertNotIn(missing,actual['text'])

    def test_generation_keeps_citations_review_and_theoretical_evidence(self):
        statement='For a finite-dimensional vector space every basis has the same size.'
        sources=[passage('theorem',statement)]
        research=research_for(sources,{'theorem':statement})
        packed=pack_context(sources,[],[],[],Config(context_tokens=1200),research)
        class OfflineModel:
            last_finish_reason='stop'
            name='offline-fixture'
            def chat(self,prompt,**kwargs):
                self.prompt=prompt
                marker=re.search(r'<!-- ANSWER_COMPLETE_[a-f0-9]+ -->',prompt).group()
                return ('Every basis has the same size in finite dimensions [0].\n'
                        '<!-- CLINKRAG_EVIDENCE_REVIEW -->\n'
                        'The source states the theorem; its proof is not included [0].\n'+marker)
        model=OfflineModel()
        result=generate('What guarantees the dimension is well-defined?',packed,model,Config(),research=research)
        self.assertIn('finite dimensions',result['answer'])
        self.assertIn('proof is not included',result['evidence_review'])
        self.assertTrue(result['completion']['complete'])
        self.assertEqual(result['sources'][0]['text'],statement)
        self.assertFalse(result['citation_audit']['invalid'])
        self.assertEqual(json.loads(packed['context'])['research_plan']['evidence_mode'],'theoretical')


if __name__=='__main__':unittest.main()
