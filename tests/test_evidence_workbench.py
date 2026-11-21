"""Checks for the evidence-to-export path and model reporting of insufficient support."""
from io import BytesIO
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'longans')]
from debug_ui.brief import make_brief, quantities_supported
from debug_ui.literature import EXAMPLE, ServiceUnavailable, literature_search, read_pdf


class WorkbenchEvidenceTests(unittest.TestCase):
    def test_quoted_quantity_rejects_spurious_doubling(self):
        quote='The students gained 50% to 90% more than the other groups.'
        self.assertFalse(quantities_supported('增益高出50%至90%，学习效率翻倍。',quote))
        self.assertFalse(quantities_supported('增益为95%。',quote))
        self.assertTrue(quantities_supported('增益高出50%至90%。',quote))
    def test_exported_source_matches_personal_text_and_page(self):
        page1='Background on energy demand.'
        page2='Wind turbines produced more energy during winter.'
        body=page1+'\n\n'+page2
        result=literature_search({'collection':'personal','question':'winter wind turbines',
            'papers':[{'title':'Energy observations','text':body,'pages':[
                {'page':4,'start':0,'end':len(page1)}, {'page':5,'start':len(page1)+2,'end':len(body)}]}]})
        item=result['items'][0]
        self.assertEqual(item['quote'],body[item['start']:item['end']])
        self.assertEqual(item['page_end'],5)
        self.assertIn('PDF 物理页码',result['markdown'])
        self.assertIn('TI  - Energy observations',result['ris'])

    def test_bundled_exports_credit_source(self):
        result=literature_search({'question':EXAMPLE, 'limit':1})
        source=result['items'][0]
        self.assertIn(source['doi'],result['ris'])
        self.assertIn(source['license'],result['markdown'])
        self.assertIn(source['authors'][0],result['markdown'])

    def test_brief_requires_both_verbatim_text_and_review(self):
        items=[{'paper_id':'doc', 'title':'Classroom study','quote':'Spacing did not improve final test retention in this classroom.'}]
        rows=[{'paper_id':'doc','claim':'Retention improved','quote':items[0]['quote']},
              {'paper_id':'other','claim':'Invalid source','quote':items[0]['quote']},
              {'paper_id':'doc','claim':'Invalid quote','quote':'a fabricated improvement of 20%'}]
        model=Mock(side_effect=[{'findings':rows},{'supported_indices':[]}])
        brief=make_brief({'question':'Did retention improve?', 'items':items},{},model)
        self.assertEqual(brief['findings'],[])
        self.assertEqual(brief['checked'],1)
        self.assertEqual(model.call_args_list[-1].args[2]['sources'][0]['quote'],items[0]['quote'])

    def test_review_failure_leaves_no_apparently_successful_findings(self):
        row={'paper_id':'x','title':'A','quote':'No effect was observed.'}
        model=Mock(side_effect=[{'findings':[{**row,'claim':'No effect'}]}, {'supported_indices':[5]}])
        with self.assertRaises(ServiceUnavailable):
            make_brief({'question':'Any effect?', 'items':[row]}, {},model)

    def test_personal_limits_and_empty_pdf(self):
        from pypdf import PdfWriter
        writer=PdfWriter()
        writer.add_blank_page(width=100,height=100)
        stream=BytesIO()
        writer.write(stream)
        with self.assertRaisesRegex(ValueError, 'OCR'):
            read_pdf(stream.getvalue())
        with self.assertRaisesRegex(ValueError, '连续'):
            read_pdf(stream.getvalue(),2,2)
        with self.assertRaisesRegex(ValueError, 'http'):
            literature_search({'question':'test query','collection':'personal',
                               'papers':[{'text':'test','title':'test','url':'file:///private'}]})
