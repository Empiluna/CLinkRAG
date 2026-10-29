"""Offline contract regressions, not a benchmark of a live model's judgments."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from clinkrag.coverage import assess, constrain_paths, coverage, evidence_scope, select_diverse
from clinkrag.structured import StructuredOutputError


class FixedModel:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.prompts = []

    def json(self, prompt, **kwargs):
        self.prompts.append(prompt)
        result = self.outputs.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def item(pid, quote, kind='empirical', contribution='finding', dimension='d1', verdict='direct'):
    return {'paperId': pid, 'relevance': {'verdict': verdict, 'quote': quote, 'reason': 'Addresses the question task.'},
            'dimensions': [{'id': dimension, 'quote': quote}] if dimension else [],
            'kind': kind, 'kind_quote': quote,
            'contribution': {'type': contribution, 'quote': quote},
            'population': {'value': 'unknown', 'quote': ''},
            'design': {'value': 'unknown', 'quote': ''}, 'period': {'value': 'unknown', 'quote': ''}}


def assess_items(papers, items, **plan):
    model = FixedModel([{'papers': items}])
    default = {'question': 'What is the evidence for the topic?', 'question_type': 'overview',
               'dimensions': [{'id': 'd1', 'label': 'Main subject'}, {'id': 'd2', 'label': 'Alternative view'}]}
    default.update(plan)
    return assess(papers, default, model, None), model


class EvidenceSelectionTests(unittest.TestCase):
    def test_direct_contribution_preserves_theory_history_engineering_review_and_resource(self):
        cases = [
            ('math', 'We prove a convergence theorem for bounded monotone sequences.', 'theoretical', 'theory', 'proof'),
            ('history', 'Archival analysis traces changes in women\'s inheritance rights in late imperial China.', 'interpretation', 'interpretation', 'history'),
            ('engineering', 'We introduce a fault tolerant design for distributed battery management systems.', 'methodological', 'method', 'design'),
            ('review', 'This systematic review synthesizes research on migration and urban housing access.', 'review', 'synthesis', 'overview'),
            ('dataset', 'We release a multilingual corpus of oral histories for dialect preservation research.', 'resource', 'resource', 'focused'),
            ('medicine', 'A randomized trial compares blood pressure outcomes in 230 adult participants.', 'empirical', 'comparison', 'comparison'),
        ]
        for pid, abstract, kind, role, task in cases:
            with self.subTest(domain=pid):
                paper = {'paperId': pid, 'title': pid, 'abstract': abstract}
                annotations, model = assess_items([paper], [item(pid, abstract, kind, role, dimension=None)],
                    question_type=task, evidence_mode='mixed', evidence_needs=['A substantive answer to this task'])
                self.assertEqual(annotations[pid]['kind'], kind)
                self.assertEqual(annotations[pid]['contribution']['type'], role)
                self.assertEqual(annotations[pid]['population']['value'], 'unknown')
                self.assertEqual([p['paperId'] for p in select_diverse([paper], annotations, 3)], [pid])
                self.assertIn('Empirical samples are NOT required', model.prompts[0])
                self.assertIn('proof/theory question', model.prompts[0])
                self.assertIn('humanities/history questions', model.prompts[0])

    def test_short_chinese_evidence_and_source_whitespace_keep_original_spans(self):
        source = '通过档案分析揭示制度变化。'
        spaced = 'The theorem\n establishes convergence under boundedness assumptions.'
        papers = [{'paperId': 'zh', 'title': '制度史', 'abstract': source},
                  {'paperId': 'math', 'title': 'Convergence', 'abstract': spaced}]
        annotations, _ = assess_items(papers, [item('zh', source, 'interpretation'),
            item('math', 'The theorem establishes convergence under boundedness assumptions.', 'theoretical')])
        self.assertLess(len(source), 20)
        self.assertEqual(annotations['zh']['relevance']['verdict'], 'direct')
        self.assertEqual(annotations['math']['relevance']['quote'], spaced)
        self.assertEqual(annotations['math']['dimensions'][0]['quote'], spaced)

    def test_keywords_title_only_fabricated_and_unrelated_evidence_stay_excluded(self):
        source = 'A longitudinal study evaluates smoking cessation advertising in American adults.'
        title = 'Japanese anime and global popularity'
        papers = [{'paperId': pid, 'title': title, 'abstract': source}
                  for pid in ('title', 'invented', 'keyword', 'unrelated', 'uncertain')]
        outputs = [item('title', title), item('invented', 'Japanese anime is popular because advertising builds fan communities.'),
                   item('keyword', 'advertising'), item('unrelated', source, verdict='unrelated'),
                   item('uncertain', source, verdict='uncertain')]
        annotations, _ = assess_items(papers, outputs, question='Why is Japanese anime popular globally?')
        self.assertEqual(select_diverse(papers, annotations, 20), [])
        self.assertTrue(all(not a['dimensions'] for a in annotations.values()))
        self.assertTrue(all(a['contribution']['type'] == 'unknown' for a in annotations.values()))

    def test_fabricated_kind_and_contribution_do_not_get_diversity_credit(self):
        source = 'A historical interpretation examines rituals in nineteenth century rural communities.'
        paper = {'paperId': 'p', 'title': 'Rituals', 'abstract': source}
        response = item('p', source, 'theoretical', 'theory')
        response['kind_quote'] = response['contribution']['quote'] = 'We prove a formal theorem.'
        annotations, _ = assess_items([paper], [response])
        self.assertEqual(annotations['p']['kind'], 'unknown')
        self.assertEqual(annotations['p']['contribution']['type'], 'unknown')
        selected = select_diverse([paper], annotations, 1)
        self.assertEqual(selected[0]['selection_signals']['kind_gain'], 0)
        self.assertEqual(selected[0]['selection_signals']['contribution_gain'], 0)

    def test_backward_compatible_assessment_without_contribution_is_usable(self):
        source = 'This review synthesizes evidence on ceramic production in medieval settlements.'
        paper = {'paperId': 'p', 'title': 'Ceramics', 'abstract': source}
        response = item('p', source, 'review')
        response.pop('contribution')
        annotations, _ = assess_items([paper], [response])
        self.assertEqual(annotations['p']['contribution'], {'type': 'unknown', 'quote': ''})
        self.assertEqual(len(select_diverse([paper], annotations, 1)), 1)

    def test_duplicate_paper_ids_doi_and_exact_content_do_not_consume_slots(self):
        source = 'This review synthesizes evidence on ceramic production in medieval settlements.'
        other = 'Experimental archaeology reconstructs kiln temperatures and fuel use in historical ceramic production.'
        papers = [{'paperId': 'p1', 'title': 'Ceramic production', 'abstract': source, 'externalIds': {'DOI': '10.1000/ABC'}},
                  {'paperId': 'p1', 'title': 'Ceramic production', 'abstract': source},
                  {'paperId': 'p2', 'title': 'Alternate metadata', 'abstract': source, 'doi': 'https://doi.org/10.1000/abc'},
                  {'paperId': 'p3', 'title': 'Ceramic production', 'abstract': source},
                  {'paperId': 'p4', 'title': 'Ceramic production', 'abstract': other}]
        unique = [papers[0], *papers[2:]]
        annotations, _ = assess_items(unique, [item(p['paperId'], p['abstract']) for p in unique])
        self.assertEqual([p['paperId'] for p in select_diverse(papers, annotations, 10)], ['p1', 'p4'])

    def test_close_ranked_chinese_papers_add_a_new_supported_direction(self):
        texts = ['通过历史档案考察传统城市的商业网络形成过程，关注商人组织与行业制度的互动机制。',
                 '通过历史档案考察传统城市的商业网络形成过程，关注商人组织与行业制度的互动关系。',
                 '研究港口运输基础设施如何改变城乡商品交换路线，以及贸易扩张的区域分布。',
                 '结合历史地图考察集市与街道空间的演化过程，以及邻里组织的变化趋势。',
                 '结合历史档案研究城市商户的契约制度和公共设施维护机制。',
                 '综合讨论传统城市的组织方式及其长期历史变化。']
        papers = [{'paperId': str(i), 'title': '传统城市研究', 'abstract': t} for i, t in enumerate(texts)]
        annotations, _ = assess_items(papers, [item(str(i), t, 'interpretation', 'interpretation', dimension='d2' if i == 2 else 'd1')
                                              for i, t in enumerate(texts)])
        chosen = select_diverse(papers, annotations, 2)
        self.assertEqual([p['paperId'] for p in chosen], ['0', '2'])
        self.assertEqual(coverage(chosen, {'dimensions': [{'id': 'd1'}, {'id': 'd2'}]})[1]['paper_ids'], ['2'])

    def test_opposite_mathematical_conditions_are_not_content_duplicates(self):
        texts = ['We prove convergence of the iteration for parameter x < 0 under boundedness assumptions.',
                 'We prove convergence of the iteration for parameter x > 0 under boundedness assumptions.']
        papers = [{'paperId': str(i), 'title': 'Convergence theorem', 'abstract': text} for i, text in enumerate(texts)]
        annotations, _ = assess_items(papers, [item(str(i), text, 'theoretical', 'theory') for i, text in enumerate(texts)])
        self.assertEqual(len(select_diverse(papers, annotations, 2)), 2)

    def test_diversity_does_not_fill_with_uncertain_or_override_large_rank_gaps(self):
        papers = [{'paperId': str(i), 'title': f'Paper {i}', 'abstract': f'The archive documents distinct historical changes in settlement number {i}.'}
                  for i in range(6)]
        outputs = [item(str(i), p['abstract'], 'interpretation', dimension='d2' if i == 5 else 'd1',
                        verdict='uncertain' if i in (1, 2, 3, 4) else 'direct') for i, p in enumerate(papers)]
        annotations, _ = assess_items(papers, outputs)
        chosen = select_diverse(papers, annotations, 10)
        self.assertEqual([p['paperId'] for p in chosen], ['0', '5'])
        self.assertEqual(select_diverse(papers, annotations, 0), [])
        self.assertEqual(select_diverse(papers, annotations, 1)[0]['paperId'], '0')

    def test_original_assessments_and_documents_are_not_mutated(self):
        source = 'This review synthesizes evidence on ceramic production in medieval settlements.'
        papers = [{'paperId': 'p', 'title': 'Ceramics', 'abstract': source}]
        annotations, _ = assess_items(papers, [item('p', source)])
        originals = copy.deepcopy((papers, annotations))
        select_diverse(papers, annotations, 1)
        self.assertEqual((papers, annotations), originals)

    def test_empty_or_malformed_batch_recovers_without_accepting_missing_evidence(self):
        self.assertEqual(assess([], {}, FixedModel([]), None), {})
        source = 'The archive documents changes in settlement patterns over two centuries.'
        papers = [{'paperId': 'a', 'title': 'A', 'abstract': source}, {'paperId': 'b', 'title': 'B', 'abstract': source}]
        model = FixedModel([{'papers': [None]}, {'papers': [item('a', source)]}, StructuredOutputError('incomplete')])
        annotations = assess(papers, {'question': 'Settlement history', 'dimensions': []}, model, None)
        self.assertEqual(annotations['a']['relevance']['verdict'], 'direct')
        self.assertEqual(annotations['b']['status'], 'unavailable')
        self.assertEqual([p['paperId'] for p in select_diverse(papers, annotations, 2)], ['a'])

    def test_nonempirical_sources_do_not_become_valid_cross_paper_causal_chains(self):
        quote = 'The theorem proves convergence under boundedness and continuity assumptions.'
        paper = {'paperId': 'a', 'title': 'Theorem', 'abstract': quote}
        annotations, _ = assess_items([paper], [item('a', quote, 'theoretical', 'theory')])
        research = {'papers': [dict(paper, assessment=annotations['a']),
                               {'paperId': 'b', 'title': 'Interpretation', 'assessment': {'kind': 'interpretation'}}]}
        single = {'id': 'single', 'paper_ids': ['a'], 'checks': []}
        cross = {'id': 'cross', 'paper_ids': ['a', 'b'], 'checks': [{'state': 'compatible'}]}
        accepted, rejected = constrain_paths([single, cross], research)
        self.assertEqual(accepted, [single])
        self.assertEqual(rejected[0]['path_id'], 'cross')

    def test_evidence_scope_does_not_expose_annotations_from_omitted_abstract_text(self):
        first = 'We evaluate changes in urban settlement using archival records and historical maps.'
        second = 'The records cover migration patterns between 1850 and 1910 in coastal cities.'
        paper = {'paperId': 'p', 'title': 'Settlement', 'abstract': first + ' ' + second}
        response = item('p', first, 'interpretation', 'interpretation')
        response['dimensions'].append({'id': 'd2', 'quote': second})
        response['design'] = {'value': 'archival analysis', 'quote': first}
        response['period'] = {'value': '1850–1910', 'quote': second}
        annotations, _ = assess_items([paper], [response])
        original = copy.deepcopy(annotations['p'])
        research = {'papers': [dict(paper, assessment=annotations['p'])],
                    'plan': {'question_type': 'history', 'evidence_mode': 'interpretive',
                             'dimensions': [{'id': 'd1'}, {'id': 'd2'}]}}
        packed = {'passages': [{'id': 'p:1', 'paper_id': 'p', 'text': second}]}
        scope = evidence_scope(packed, research)
        clipped = scope['sources'][0]['assessment']
        self.assertEqual(scope['dimensions'][0]['paper_ids'], [])
        self.assertEqual(scope['dimensions'][1]['paper_ids'], ['p'])
        self.assertEqual(clipped['kind'], 'unknown')
        self.assertEqual(clipped['contribution']['type'], 'unknown')
        self.assertEqual(clipped['design']['value'], 'unknown')
        self.assertEqual(clipped['relevance']['verdict'], 'uncertain')
        self.assertEqual(clipped['period']['value'], '1850–1910')
        self.assertEqual(annotations['p'], original)


if __name__ == '__main__':
    unittest.main()
