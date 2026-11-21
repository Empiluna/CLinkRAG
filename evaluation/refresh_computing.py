"""Rebuild the licensed computing proceedings snapshot from publisher metadata.

Run from the project root: python -m evaluation.refresh_computing
Only the maintainer's refresh downloads data. Runtime search uses the checked-in file.
"""
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

import requests
import yaml

from debug_ui.literature import PlainAbstract

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / 'clinkrag/data/computing.jsonl'
ACL_REV = '37f8244b23f7647a84173868f26bb0f52fb2cb77'
CC_BY = 'https://creativecommons.org/licenses/by/4.0/'
PMLR = 'https://proceedings.mlr.press/v238/'
DROPS = {'ICDT': '数据库理论', 'DISC': '分布式计算', 'ESA': '算法与数据结构',
         'ECOOP': '程序设计语言', 'ECRTS': '实时系统'}


def clean(value):
    return ' '.join(str(value or '').split())


def xml_text(node):
    return clean(''.join(node.itertext())) if node is not None else ''


def get(session, url, **params):
    response = session.get(url, params=params, timeout=(8, 90))
    response.raise_for_status()
    return response


def acl(session):
    url = f'https://raw.githubusercontent.com/acl-org/acl-anthology/{ACL_REV}/data/xml/2024.eacl.xml'
    collection = ET.fromstring(get(session, url).content)
    for volume in collection.findall('volume'):
        part = volume.get('id')
        if part not in ('long', 'short'):
            continue
        for paper in volume.findall('paper'):
            abstract = xml_text(paper.find('abstract'))
            if not abstract:
                continue
            doi = xml_text(paper.find('doi'))
            authors = [clean(' '.join(a.findtext(k, '') for k in ('first', 'last'))) for a in paper.findall('author')]
            yield dict(paper_id=doi, doi=doi, url=f'https://aclanthology.org/2024.eacl-{part}.{paper.get("id")}/',
                       title=xml_text(paper.find('title')), text=abstract, authors=authors,
                       page=paper.findtext('pages',''), container='EACL 2024', domain='自然语言处理', year=2024)


def aistats(session):
    records = yaml.safe_load(get(session, PMLR+'assets/bib/citeproc.yaml').content)
    for record in records:
        if not record.get('abstract') or record.get('type') == 'book':
            continue
        url = record['URL']
        if not url.startswith(PMLR) or not url.endswith('.html'):
            raise ValueError(f'Invalid PMLR publication URL {url}')
        authors = [clean(' '.join(a.get(k,'') or '' for k in ('given', 'family'))) for a in record['author']]
        yield dict(paper_id=url, url=url, title=clean(record['title']), text=clean(record['abstract']),
                   authors=authors, year=2024, container='AISTATS 2024', domain='机器学习与统计',
                   volume='238', page=clean(record.get('page')))


def dagstuhl(session):
    for venue, field in DROPS.items():
        prefix = f'10.4230/lipics.{venue.lower()}.2025.'
        response = get(session, 'https://api.datacite.org/dois', query='doi:'+prefix+'*',
                       **{'page[size]':1000, 'fields[dois]':'doi,creators,titles,descriptions,subjects,rightsList,types,publicationYear,url'}).json()
        if len(response['data']) != response['meta']['total']:
            raise ValueError(f'Truncated DataCite volume {venue}')
        for item in response['data']:
            a = item['attributes']
            doi = a['doi'].lower()
            if not re.fullmatch(re.escape(prefix)+r'[1-9][0-9]*', doi) or a['types']['resourceTypeGeneral'] != 'ConferencePaper':
                continue
            if not any(r.get('rightsUri','').startswith(CC_BY) for r in a.get('rightsList', [])):
                continue
            abstract = next((PlainAbstract.decode(d['description']) for d in a['descriptions']
                             if d['descriptionType']=='Abstract'), '')
            if not abstract:
                continue
            authors = [clean(' '.join([p.get('givenName','') or '', p.get('familyName','') or ''])) or p['name'] for p in a['creators']]
            yield dict(paper_id=doi, doi=doi, url='https://doi.org/'+doi, year=int(a['publicationYear']),
                       container=venue+' 2025', domain=field, authors=authors,
                       keywords=[s['subject'] for s in a.get('subjects',[]) if s.get('subject')],
                       title=clean(a['titles'][0]['title']), text=abstract)


def main():
    with requests.Session() as session:
        session.headers['User-Agent']='CLinkRAG/3 (https://github.com/Empiluna/CLinkRAG)'
        records = [p for source in (acl, aistats, dagstuhl) for p in source(session)]
    records.sort(key=lambda p:p['paper_id'])
    if len({p['paper_id'] for p in records}) != len(records):
        raise ValueError('Duplicate publication identifier')
    for p in records:
        if not all([p['paper_id'], p['authors'], all(p['authors']), p['title'], p['text']]):
            raise ValueError(f'Incomplete attribution in {p["url"]}')
        p.update(license=CC_BY, publication_type='proceedings-article')
    from collections import Counter
    venues = Counter(p['container'] for p in records)
    if len(venues) != len(DROPS)+2:
        raise ValueError(f'Missing proceedings {venues}')
    output = ''.join(json.dumps(p,ensure_ascii=False)+'\n' for p in records)
    pending = TARGET.with_suffix('.tmp')
    pending.write_text(output,encoding='utf-8',newline='\n')
    pending.replace(TARGET)
    print(len(records), dict(sorted(venues.items())))


if __name__ == '__main__':
    main()
