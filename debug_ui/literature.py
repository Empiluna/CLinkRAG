"""Read a small source collection, return attributable passages and portable notes."""
from html.parser import HTMLParser
from io import BytesIO
from collections import OrderedDict
from concurrent.futures import Future
from copy import deepcopy
from threading import Lock
from time import monotonic
from urllib.parse import quote as urlquote, urlsplit
import re

import requests


class ServiceUnavailable(Exception):
    """Expected failure of a remote service, with a message suitable for the UI."""


EXAMPLE = '放射性碳测年如何帮助判断古埃及王朝的年代？'


def read_pdf(content, first=1, last=None):
    from pypdf import PdfReader
    if not content.startswith(b'%PDF-') or len(content) > 10*1024*1024:
        raise ValueError('请选择 10 MB 以内的 PDF 文件。')
    try:
        reader = PdfReader(BytesIO(content))
        if reader.is_encrypted:
            raise ValueError('请先用 PDF 阅读器解除密码保护。')
        count = len(reader.pages)
        last = count if last is None else last
        if not 1 <= first <= last <= count or last-first >= 100:
            raise ValueError(f'文件共 {count} 页，请指定连续的 1–100 页。')
        pieces, pages, end = [], [], 0
        for n in range(first, last+1):
            text = (reader.pages[n-1].extract_text() or '').strip()
            if not text:
                continue
            start = end + (2 if pieces else 0)
            end = start+len(text)
            if end > 50000:
                raise ValueError('所选页的文字超过 5 万字，请缩小页码范围再导入。')
            pieces.append(text)
            pages.append({'page':n, 'start':start,'end':end})
        if not pages:
            raise ValueError('所选页没有可复制的文字。请先用 OCR 识别扫描件，或粘贴原文。')
        title = str((reader.metadata or {}).get('/Title') or '')[:500]
        return {'text':'\n\n'.join(pieces), 'pages':pages, 'title':title, 'page_count':count}
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError('无法解析这份 PDF，请尝试重新导出文件或粘贴文本。') from exc


def field(value, label, maximum, minimum=0):
    if not isinstance(value, str) or not minimum <= len(value.strip()) <= maximum:
        raise ValueError(f'{label}长度应为 {minimum}–{maximum} 个字符。')
    return value.strip()


def source_url(value):
    if not value:
        return ''
    parts = urlsplit(field(value, '来源链接', 2000, 1))
    if parts.scheme not in ('http', 'https') or not parts.hostname or parts.username or parts.password:
        raise ValueError('来源链接须使用 http 或 https。')
    return parts.geturl()


class PlainAbstract(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)

    def handle_endtag(self, tag):
        if tag.split(':')[-1] in ('p', 'title', 'sec'):
            self.parts.append(' ')

    @classmethod
    def decode(cls, value):
        parser = cls()
        parser.feed(value)
        parser.close()
        return ' '.join(''.join(parser.parts).split())


def crossref_papers(question, limit):
    # Crossref's rows parameter controls the candidate pool. Searches requesting
    # equivalent pools can reuse metadata even when the number displayed differs.
    key = (' '.join(question.split()), min(40, max(15, 4*limit)))
    with _crossref_lock:
        cached = _crossref_cache.get(key)
        if cached and cached[0] > monotonic():
            _crossref_cache.move_to_end(key)
            return deepcopy(cached[1])
        _crossref_cache.pop(key, None)
        pending = _crossref_pending.get(key)
        if pending is None:
            pending = _crossref_pending[key] = Future()
            fetch = True
        else:
            fetch = False
    if not fetch:
        return deepcopy(pending.result())
    try:
        rows = _fetch_crossref(*key)
        with _crossref_lock:
            if rows:
                _crossref_cache[key] = (monotonic()+300, rows)
                if len(_crossref_cache) > 32:
                    _crossref_cache.popitem(last=False)
            pending.set_result(rows)
        return deepcopy(rows)
    except Exception as error:
        pending.set_exception(error)
        raise
    finally:
        with _crossref_lock:
            _crossref_pending.pop(key, None)


_crossref_cache = OrderedDict()
_crossref_pending = {}
_crossref_lock = Lock()


def _fetch_crossref(question, rows):
    endpoint = 'https://api.crossref.org/works'
    params = {'query.bibliographic': question, 'rows': rows,
              'filter': 'has-abstract:true',
              'select': 'DOI,title,abstract,published,author,type,container-title,volume,issue,page'}
    try:
        with requests.get(endpoint, params=params, timeout=(5, 18), headers={
                'User-Agent': 'CLinkRAG/2 (https://github.com/Empiluna/CLinkRAG)',
                'Accept': 'application/json'}) as response:
            response.raise_for_status()
            works = response.json()['message']['items']
    except (requests.RequestException, KeyError, ValueError, TypeError) as exc:
        raise ServiceUnavailable('Crossref 暂时无法返回论文。可稍后重试，或用自带文献和自己的材料继续查证。') from exc
    papers = []
    seen = set()
    for work in works:
        doi = work.get('DOI', '').lower()
        titles = work.get('title') or []
        abstract = PlainAbstract.decode(work.get('abstract') or '')
        if not doi or doi in seen or not titles or not abstract:
            continue
        seen.add(doi)
        dates = work.get('published', {}).get('date-parts') or [[]]
        authors = [' '.join(filter(None, [a.get('given'), a.get('family')])) or a.get('name','')
                   for a in work.get('author', []) if isinstance(a, dict)]
        papers.append({'paper_id':doi, 'title':PlainAbstract.decode(titles[0]), 'text':abstract,
                       'url':'https://doi.org/'+urlquote(doi, safe='/()'), 'doi':doi,
                       'year':dates[0][0] if dates[0] else '', 'authors':authors,
                       'publication_type':work.get('type',''), 'container':(work.get('container-title') or [''])[0],
                       'volume':work.get('volume',''), 'issue':work.get('issue',''), 'page':work.get('page','')})
    return papers


def personal_papers(papers):
    if not isinstance(papers, list) or not 1 <= len(papers) <= 20:
        raise ValueError('请提供 1–20 篇材料，每篇包含标题与原文。')
    sources = []
    for i, row in enumerate(papers, 1):
        if not isinstance(row, dict):
            raise ValueError('材料格式无效。')
        original = row.get('text')
        field(original, '单篇原文', 50000, 1)
        if len(original) > 50000:
            raise ValueError('单篇原文最多 50000 个字符。')
        sources.append({'paper_id':f'local-{i}', 'title':field(row.get('title'), '标题', 500, 1),
                        'text':original, 'url':source_url(row.get('url')),
                        'year':field(str(row.get('year') or ''), '年份', 12)})
        if 'pages' in row:
            pages = row['pages']
            if not isinstance(pages,list) or len(pages)>100:
                raise ValueError('PDF 页码记录无效。')
            end, page = 0, 0
            for span in pages:
                if (not isinstance(span,dict) or any(type(span.get(k)) is not int for k in ('page','start','end'))
                        or span['page'] <= page or not end <= span['start'] < span['end'] <= len(original)):
                    raise ValueError('PDF 字符位置与页码不一致。')
                end, page = span['end'],span['page']
            sources[-1]['pages'] = pages
    if sum(len(row['text']) for row in sources) > 300000:
        raise ValueError('本次材料合计最多 300000 个字符。')
    return sources


def single_line(value):
    return ' '.join(str(value or '').split())


def exports(question, items, note):
    notes = ['# '+single_line(question), '', note, '']
    records = []
    for index, item in enumerate(items, 1):
        title, url, passage = item['title'], item.get('url') or '', item['quote']
        notes.extend([f'## [{index}] {single_line(title)}', '', *['> '+s for s in passage.splitlines()], '',
                      f'原文字符位置 {item["start"]}–{item["end"]}（起点从 0 计，终点不含）。',
                      single_line(url), ''])
        if item.get('page_start'):
            notes.append(f'PDF 物理页码 {item["page_start"]}–{item["page_end"]}')
        if item.get('container'):
            notes.append('出版信息　'+' · '.join(single_line(v) for v in (item['container'],str(item.get('year') or ''),item.get('page')) if v))
        if item.get('license'):
            notes.extend(['作者　'+', '.join(item.get('authors') or []),
                          '原文许可　'+single_line(item['license']), ''])
        kinds = {'journal-article':'JOUR', 'book':'BOOK', 'monograph':'BOOK', 'book-chapter':'CHAP',
                 'proceedings-article':'CPAPER', 'dissertation':'THES', 'report':'RPRT',
                 'dataset':'DATA', 'posted-content':'UNPB'}
        kind = kinds.get(item.get('publication_type'), 'JOUR' if item.get('license') else 'GEN')
        record = ['TY  - '+kind,
                  'TI  - '+single_line(title)]
        authors = item.get('authors') or []
        if isinstance(authors,str):
            authors = [authors]
        record.extend('AU  - '+single_line(a) for a in authors if isinstance(a,str) and a.strip())
        pagination = re.split(r'[-–—]', single_line(item.get('page')), maxsplit=1)
        if pagination[0]:
            record.append('SP  - '+pagination[0])
        if len(pagination)==2 and pagination[1]:
            record.append('EP  - '+pagination[1])
        for tag, value in [('PY', item.get('year')), ('UR', url), ('DO',item.get('doi')),
                           ('T2',item.get('container')),('VL',item.get('volume')),('IS',item.get('issue'))]:
            if value:
                record.append(tag+'  - '+single_line(value))
        records.append('\r\n'.join(record+['ER  - ']))
    return '\n'.join(notes), '\r\n\r\n'.join(records)


def literature_search(data):
    from clinkrag.library import search_library
    if not isinstance(data, dict):
        raise ValueError('请提供研究问题和文献范围。')
    question = field(data.get('question'), '问题', 1500, 2)
    english_query = field(data.get('english_query', ''), '英文检索词', 240)
    limit = data.get('limit', 5)
    if type(limit) is not int or not 1 <= limit <= 10:
        raise ValueError('展示数量应为 1–10。')
    collection = data.get('collection', 'builtin')
    retrieval_query = question+' '+english_query if english_query else question
    papers = None
    if collection == 'personal':
        papers = personal_papers(data.get('papers'))
        note = '在本次提供的材料中查找原句。'
    elif collection == 'crossref':
        papers = crossref_papers(english_query or question, limit)
        note = '来源为 Crossref 收录的论文摘要。字符位置相对于清理排版标签后的摘要。'
    elif collection == 'builtin':
        note = '来源为随包开放文献。字符位置相对于收录文本。'
    elif collection == 'computing':
        note = '来源为随包计算机与 AI 会议摘要。摘录位置对应随包保存的原摘要。'
    else:
        raise ValueError('请选择有效的文献范围。')
    if collection == 'computing':
        from clinkrag.computing import search_computing
        result = search_computing(retrieval_query, limit)
    else:
        result = search_library(retrieval_query, papers=papers, limit=limit)
    result.update(question=question, english_query=english_query)
    if english_query:
        note += ' 本次补充检索词为 '+single_line(english_query)+'。'
    if papers is not None:
        metadata = {p['paper_id']:p for p in papers}
        for item in result['items']:
            original = metadata[item['paper_id']]
            item.update({k:original[k] for k in ('authors','doi','publication_type','container','volume','issue','page')
                         if k in original})
            pages=[span['page'] for span in original.get('pages',[]) if
                   span['start'] < item['end'] and span['end'] > item['start']]
            if pages:
                item.update(page_start=pages[0], page_end=pages[-1])
    if not result['items']:
        note += ' 本次没有找到匹配的原文，可以更换关键词或增加材料。'
    markdown, ris = exports(question, result['items'], note)
    return {**result, 'collection':collection, 'note':note, 'markdown':markdown, 'ris':ris}
