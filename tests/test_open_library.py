"""The public library must return real indexed text in its original coordinates."""
import json
from pathlib import Path
import unittest

from clinkrag.library import load_library, search_library
from clinkrag.retrieval import LexicalIndex, lexical_scores


class OpenLibraryTests(unittest.TestCase):
    def test_absent_material_stays_empty(self):
        self.assertEqual(search_library('nonexistentxyz quasarfoo')['items'],[])
        self.assertEqual(search_library('How does the study work?', papers=[])['items'],[])
        self.assertEqual(search_library('如何研究', papers=[{'title':'磁性','text':'磁性材料的表征。'}])['items'],[])

    def test_works_without_metadata_preserves_user_source_and_offsets(self):
        text='  这是一段普通说明。  阳极氧化可以改变薄膜厚度。\n这一结果对本组材料适用。  '
        items=search_library('阳极氧化',papers=[{'title':'材料实验记录','text':text}])['items']
        self.assertEqual(len(items),1)
        self.assertEqual(items[0]['quote'],text[items[0]['start']:items[0]['end']])
        self.assertIn('改变薄膜厚度',items[0]['quote'])
        self.assertEqual(items[0]['url'],'')
        self.assertIsNone(items[0]['year'])

    def test_titles_and_keywords_are_never_manufactured_as_source_text(self):
        original='This report evaluates classroom physics instruction. The intervention took place during a school term.'
        record={'paper_id':'x','title':'Study of lessons','text':original,'keywords':['间隔学习'],
                'authors':['Example Author'],'url':'javascript:alert(1)'}
        result=search_library('间隔学习',papers=[record,record])
        self.assertEqual(len(result['items']),1)
        item=result['items'][0]
        self.assertEqual(item['match_basis'],'title_or_keywords')
        self.assertEqual(item['quote'],original[item['start']:item['end']])
        self.assertEqual(item['url'],'')

    def test_all_publisher_sources_are_attributed_and_have_verifiable_examples(self):
        # A Chinese catalogue keyword matches an English abstract whose actual
        # result is in the middle, followed by limitations and availability.
        question='情感分析'
        original=('We study polarity in short messages. Context-dependent ratings improved agreement. '
                  'The study was limited to one corpus. Software is publicly available.')
        record={'title':'Contextual polarity','text':original,'keywords':['情感分析']}
        sample=search_library(question,papers=[record])['items'][0]
        self.assertEqual(sample['quote'],original)
        self.assertEqual(sample['match_basis'],'title_or_keywords')
        papers=load_library()
        self.assertEqual(len({p['paper_id'] for p in papers}),len(papers))
        for row in papers:
            self.assertTrue(row['authors'])
            self.assertIn('Creative Commons',row['license_statement'])
            self.assertEqual(row['url'],'https://doi.org/'+row['doi'])
            self.assertTrue(row['source_xml'].startswith('https://journals.plos.org/'))
            matches=search_library(row['example_question'])['items']
            hit=next(p for p in matches if p['paper_id']==row['paper_id'])
            self.assertEqual(hit['quote'],row['text'][hit['start']:hit['end']])
        papers[0]['text']='changed'
        self.assertNotEqual(load_library()[0]['text'],'changed')

    def test_reuse_of_index_preserves_other_queries_and_zero_scores(self):
        texts=['段落数字 13.7','An example with exact decimal 13.7.','An unrelated article.']
        index=LexicalIndex(texts)
        for query in ['13.7','段落','example','nothing_matches']:
            self.assertEqual(index.scores(query),lexical_scores(query,texts))

    def test_tail_of_unpunctuated_table_retains_actual_search_hit(self):
        body='column row 123 '*920 + ' measurement of quaternionic symmetry'
        hit=search_library('quaternionic',papers=[{'title':'Table A','text':body}])['items'][0]
        self.assertIn('quaternionic',hit['quote'])
        self.assertGreater(hit['start'],4000)
        self.assertLessEqual(len(hit['quote']),4000)
        self.assertEqual(hit['quote'],body[hit['start']:hit['end']])


if __name__=='__main__':
    unittest.main()
