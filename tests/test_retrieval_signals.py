"""Synthetic mechanism checks, not a benchmark of model accuracy across disciplines."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from clinkrag.core import Config, build_paths, compatible, prepare_corpus
from clinkrag.retrieval import (assessment_pool, clean_queries, fuse_rankings,
                               lexical_scores, query_key, search_query, terms)


class RetrievalSignalsTests(unittest.TestCase):
    def test_domain_terms_survive_lexical_ranking(self):
        examples = [
            ('mathematics', 'compactness theorem proof', 'A proof of the compactness theorem under explicit logical assumptions.'),
            ('physics', 'quantum spin Hall effect', 'Edge states and the quantum spin Hall effect in a two dimensional system.'),
            ('computing', 'retrieval augmented generation', 'Grounded answers with retrieval augmented generation and source attribution.'),
            ('medicine', 'randomized diabetes intervention', 'A randomized intervention for diabetes management measured patient outcomes.'),
            ('biology', 'CRISPR gene editing', 'CRISPR gene editing targets a specific genomic sequence.'),
            ('chemistry', 'electrocatalytic carbon reduction', 'Electrocatalytic carbon reduction on copper catalysts depends on surface structure.'),
            ('materials', 'perovskite thermal stability', 'Thermal stability in perovskite films depends on composition and processing.'),
            ('ecology', 'forest biodiversity fragmentation', 'Forest fragmentation changes habitat availability and measured biodiversity.'),
            ('economics', 'inflation monetary policy', 'Inflation responses to monetary policy under heterogeneous household expectations.'),
            ('education', 'formative assessment classroom', 'Classroom formative assessment informs feedback and subsequent instruction.'),
            ('history', '明代海上贸易档案', '本文通过明代海上贸易档案分析商人与地方官府之间的经济关系。'),
            ('law', 'judicial interpretation proportionality', 'Judicial interpretation of proportionality in constitutional reasoning.'),
            ('culture', '日本动漫海外传播', '日本动漫海外传播中的字幕翻译和观众社群参与形成了不同传播路径。'),
        ]
        for field, query, source in examples:
            with self.subTest(field=field):
                scores = lexical_scores(query, [source, 'A study of smoking cessation advertising and audience survey response.'])
                self.assertGreater(scores[0], scores[1])

    def test_cjk_tokens_and_unicode_normalization(self):
        self.assertIn('理论', terms('理论证明'))
        self.assertIn('证明', terms('理论证明'))
        self.assertEqual(terms('ＢＥＲＴ'), terms('bert'))
        self.assertEqual(lexical_scores('absent', ['one text', 'another']), [0.0, 0.0])

    def test_query_validation_and_search_normalization(self):
        self.assertEqual(clean_queries(['CRISPR', '中文论文', 'crispr', '', None]), ['CRISPR', '中文论文'])
        self.assertEqual(clean_queries(['valid query'], maximum=0), [])
        self.assertEqual(search_query('  COVID-19  T-cell  '), 'COVID 19 T cell')
        self.assertEqual(query_key('Self-RAG'), query_key('SELF  RAG'))

    def test_duplicate_query_alias_does_not_change_ranking(self):
        papers = [{'paperId': str(i), 'title': 'Graph retrieval', 'abstract': 'Graph retrieval evidence.',
                   'score': 10-i, 'query_ranks': {'graph retrieval': i+1}}
                  for i in range(3)]
        plan = {'topic_queries': ['graph retrieval'], 'dimensions': []}
        before = fuse_rankings('graph retrieval', papers, plan)
        papers[-1]['query_ranks']['GRAPH  RETRIEVAL'] = 3
        after = fuse_rankings('graph retrieval', papers, plan)
        self.assertEqual([(p['paperId'], p['fusion_score']) for p in before],
                         [(p['paperId'], p['fusion_score']) for p in after])

    def test_fusion_uses_ranks_and_keeps_missing_service_ranks(self):
        papers = [{'paperId': str(i), 'title': title, 'abstract': title, 'score': 10-i}
                  for i, title in enumerate(['specific material', 'another subject', 'specific material methods'])]
        before = fuse_rankings('specific material', papers, {'topic_queries': [], 'dimensions': []})
        for p in papers:
            p['score'] *= 10000
        after = fuse_rankings('specific material', papers, {'topic_queries': [], 'dimensions': []})
        self.assertEqual([p['paperId'] for p in before], [p['paperId'] for p in after])
        self.assertEqual(len(before), 3)
        self.assertTrue(all(p['ranking']['search_rank'] is None for p in before))

    def test_review_pool_budget_and_direction_reservation(self):
        papers = [{'paperId': str(i), 'queries': ['dominant' if i < 30 else 'rare']} for i in range(40)]
        plan = {'topic_queries': ['dominant'], 'dimensions': [{'id': 'd1', 'query': 'rare'}]}
        for budget in [0, 1, 2, 5, 16, 60]:
            result = assessment_pool(papers+papers, plan, budget)
            self.assertLessEqual(len(result), budget)
            self.assertEqual(len(result), len({p['paperId'] for p in result}))
        self.assertTrue(any('rare' in p['queries'] for p in assessment_pool(papers, plan, 16)))
        self.assertEqual(assessment_pool(papers, plan, 16)[0]['paperId'], '0')

    def test_cjk_sentence_windows_keep_exact_offsets(self):
        text = ''.join(f'档案{i}记载了制度变化，研究者同时注明材料的时间范围和适用限制。' for i in range(80))
        corpus = prepare_corpus([{'id': 'history', 'text': text}])
        self.assertGreater(len(corpus['passages']), 1)
        for window in corpus['passages']:
            self.assertEqual(window['text'], text[window['start']:window['end']])
        for left, right in zip(corpus['passages'], corpus['passages'][1:]):
            self.assertLessEqual(left['end'], right['start'])

    def test_scope_conflicts_outside_computing_are_not_ignored(self):
        for key in ['population', 'period', 'method', 'assumptions', 'jurisdiction']:
            with self.subTest(key=key):
                check = compatible({key: 'context one'}, {key: 'context two'})
                self.assertEqual(check['state'], 'conflict')
                self.assertIn(key, [c['field'] for c in check['conflicts']])
        self.assertEqual(compatible({}, {})['state'], 'unknown')


if __name__ == '__main__':
    unittest.main()
