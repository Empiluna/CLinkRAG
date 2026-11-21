"""Regression coverage for query routing, technical lookups, offsets and index reuse."""
import json
import unittest

from clinkrag.library import LibraryIndex, key_terms, library_features, search_library
from clinkrag.retrieval import LexicalIndex
from clinkrag.technical import concepts, identifiers


class LibraryTechniqueTests(unittest.TestCase):
    def test_chinese_method_retrieves_an_english_passage_over_an_unrelated_consensus(self):
        papers = [
            {'id':'clinical','title':'Expert consensus','text':'This consensus summarizes reported patient quality of life.'},
            {'id':'systems','title':'Replicated state','text':'Setup details. A consensus algorithm coordinates distributed processes. Other context.'},
        ]
        result = search_library('分布式共识', papers)['items']
        self.assertEqual([r['paper_id'] for r in result], ['systems'])
        item = result[0]
        self.assertIn('consensus algorithm', item['quote'])
        self.assertEqual(item['quote'],papers[1]['text'][item['start']:item['end']])
        self.assertFalse(concepts('A rag doll was seen in a shop.'))
        self.assertFalse(concepts('LoRa radio networks transmit sensor readings.'))
        self.assertNotIn('attention mechanism',concepts('Attention and distraction in children.'))

    def test_symbol_and_model_versions_remain_distinct(self):
        papers = [{'id':name, 'title':name+' implementation','text':'A small programming language study.'}
                  for name in ['C#','C++17','B tree','B+ trees','GPT4','GPT-4o']]
        for query,expected in [('C++','C++17'),('C#','C#'),('B+ tree','B+ trees'),('GPT 4o','GPT-4o')]:
            with self.subTest(query=query):
                self.assertEqual(search_library(query,papers)['items'][0]['paper_id'], expected)
        self.assertEqual(identifiers('ＡＢＣ－２.１'), frozenset({'abc2.1'}))

    def test_id_resolves_to_owner_instead_of_a_bibliographic_mention(self):
        papers = [
            {'id':'citation','title':'Another study','text':'A survey referencing 10.1234/some.id.'},
            {'id':'original','title':'The original study','doi':'10.1234/SOME.ID','text':'Findings and citation notes.'},
            {'id':'preprint','title':'A preprint','url':'https://arxiv.org/abs/2003.01234','text':'The stable abstract.'},
        ]
        self.assertEqual([i['paper_id'] for i in search_library('doi:10.1234/some.id',papers)['items']], ['original'])
        self.assertEqual(search_library('https://arxiv.org/pdf/2003.01234v2.pdf',papers)['items'][0]['paper_id'], 'preprint')
        self.assertEqual(search_library('arXiv:2401.00001',papers)['items'], [])

    def test_sentence_query_preserves_the_original_document_scoring(self):
        papers = [
            {'id':'a','title':'Fine tuning a language model','text':'Context describes language model fine tuning in a small corpus.'},
            {'id':'b','title':'Different intervention','text':'We evaluated whether the intervention improved comprehension across multiple training tasks.'},
        ]
        question='We evaluated whether fine tuning the language model improved comprehension across tasks.'
        original=LexicalIndex([p['title']+' '+p['title']+'  '+p['text'] for p in papers],tokenizer=key_terms)
        scores=original.scores(question)
        expected=[(papers[i]['id'],round(scores[i],6)) for i in sorted(range(2), key=scores.__getitem__,reverse=True)]
        actual=search_library(question,papers)['items']
        self.assertEqual([(r['paper_id'],r['score']) for r in actual],expected)

    def test_precomputed_term_rows_round_trip_and_return_independent_records(self):
        papers=[{'id':'one','title':'A query optimizer','text':'Database query planning improved. Measurements were collected.',
                 'authors':['One']},
                {'id':'two','title':'An educational survey','text':'Teacher training involved a small district.'}]
        fresh=LibraryIndex(papers)
        frozen=LibraryIndex(papers,features=json.loads(json.dumps(library_features(papers))))
        papers[0]['authors'].clear()
        for question in ['数据库查询优化','query optimizer','teacher training']:
            self.assertEqual(fresh.search(question),frozen.search(question))
        first=fresh.search('数据库查询优化')['items'][0]
        first['authors'].clear()
        self.assertEqual(fresh.search('数据库查询优化')['items'][0]['authors'],['One'])

    def test_subterm_matches_for_both_complete_and_query_specific_indexes(self):
        row={'id':'g','title':'Graph neural networks','text':'Graph neural networks encode node interactions.'}
        self.assertEqual(concepts(row['title']), {'graph neural network','neural network'})
        for query in ['神经网络','图神经网络']:
            self.assertEqual(LibraryIndex([row]).search(query),search_library(query,[row]))


if __name__=='__main__':
    unittest.main()
