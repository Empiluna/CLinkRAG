"""Rebuild the bundled library from Creative Commons publisher JATS. Run from the repository root."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import urllib.request
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'clinkrag' / 'data'


def content(node):
    return ' '.join(''.join(node.itertext()).split()) if node is not None else ''


def fetch(entry):
    number, field, terms, question = entry
    doi = '10.1371/journal.pone.' + number
    url = 'https://journals.plos.org/plosone/article/file?id=' + doi + '&type=manuscript'
    with urllib.request.urlopen(url, timeout=45) as response:
        meta = ET.fromstring(response.read()).find('./front/article-meta')
    title = content(meta.find('./title-group/article-title'))
    license_node = meta.find('./permissions/license')
    license_url = license_node.get('{http://www.w3.org/1999/xlink}href', '') if license_node is not None else ''
    if not license_url:
        license_url = next((x.get('{http://www.w3.org/1999/xlink}href') for x in license_node.iter() if 'creativecommons.org' in str(x.attrib)), '') if license_node is not None else ''
    license_statement = content(license_node)
    if not license_url and 'Creative Commons Attribution License' in license_statement:
        # Older JATS records give the grant in words without a license version.
        license_url = 'https://doi.org/' + doi
    elif not re.match(r'https?://creativecommons.org/(licenses/by/|publicdomain/zero/)', license_url or ''):
        raise ValueError('No verified reusable license for '+doi+': '+repr(license_url))
    abstract = '\n\n'.join(content(p) for p in meta.findall('./abstract//p') if content(p))
    authors = []
    for author in meta.findall('./contrib-group/contrib[@contrib-type="author"]'):
        name = author.find('name')
        if name is not None:
            authors.append(' '.join(filter(None,[content(name.find('given-names')), content(name.find('surname'))])))
        elif author.find('collab') is not None:
            authors.append(content(author.find('collab')))
    if not abstract or not authors or meta.findtext('article-id[@pub-id-type="doi"]') != doi:
        raise ValueError('Missing abstract or authors, or unexpected DOI for '+doi)
    print(number, len(abstract), license_url, flush=True)
    return dict(paper_id=doi, doi=doi, title=title, text=abstract, year=int(meta.findtext('pub-date/year')),
                authors=authors, url='https://doi.org/'+doi, license=license_url, license_statement=license_statement,
                field=field, keywords=terms, example_question=question, source_xml=url)


if __name__ == '__main__':
    entries = json.loads((DATA/'library_catalog.json').read_text(encoding='utf-8'))
    with ThreadPoolExecutor(max_workers=4) as executor:
        records = list(executor.map(fetch, entries))
    (DATA/'library.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n', encoding='utf-8')
