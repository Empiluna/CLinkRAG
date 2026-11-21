"""Exercise the reader on a publisher PDF, from a Chinese question to a cited page."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT), str(ROOT/'longans')]
import requests
from debug_ui.brief import suggest_terms
from debug_ui.literature import EXAMPLE, literature_search, read_pdf
from llms.settings import load_settings


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', required=True, action='store_true', help='Download one PLOS PDF and make one short model request for search terms')
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    doi='10.1371/journal.pone.0314612'
    url='https://journals.plos.org/plosone/article/file'
    with requests.get(url,params={'id':doi,'type':'printable'},timeout=(8,30)) as response:
        response.raise_for_status()
        raw=response.content
    pdf=read_pdf(raw,first=1,last=2)
    terms=suggest_terms({'question':EXAMPLE},load_settings())['english_query']
    paper={**pdf,'title':'Resolution of the High versus Low debate for Old and Middle Kingdom Egypt',
           'url':'https://doi.org/'+doi}
    item=literature_search({'collection':'personal','question':EXAMPLE,'english_query':terms,'papers':[paper]})['items'][0]
    exact=pdf['text'][item['start']:item['end']]==item['quote']
    report={'doi':doi,'pdf_sha256':hashlib.sha256(raw).hexdigest(),'pages_in_file':pdf['page_count'],
            'requested_pages':[1,2],'english_query':terms,'match_pages':[item['page_start'],item['page_end']],
            'exact':exact,'has_topic':any(t in item['quote'].casefold() for t in ('egypt','chronolog','radiocarbon'))}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(report)
    raise SystemExit(int(not(exact and report['has_topic'])))
