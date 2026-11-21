"""Local, extractive literature search with verifiable offsets. Standard library only."""
from functools import lru_cache
import json
from copy import deepcopy
from pathlib import Path
import re
from urllib.parse import urlparse

from .retrieval import LexicalIndex, terms

_STOP = set(('a an the in on of to as for at with by from or and how what which when can do does is '
             'are was were study paper research result results using related about across tell show '
             'influence affect evidence studies their these those some when why did be do compare '
             'there has have in this that according you please would could').split())
_CJK = re.compile(r'[\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]')
_STOP_CJK = set('如何 怎么 怎样 研究 论文 可以 影响 关系 什么 哪些 哪种 有关 是否 能否 为什么 帮助 问题 有何 之间 相关 判断 不同 有什'.split())
_DATA = Path(__file__).with_name('data')/'library.json'


def key_terms(text):
    result = []
    for term in terms(text):
        if term in _STOP or term in _STOP_CJK:
            continue
        if len(term) == 1 and (_CJK.search(term) or term.isascii() and not term.isdigit()):
            continue
        result.append(term)
    return result


@lru_cache(maxsize=1)
def _bundled():
    return json.loads(_DATA.read_text(encoding='utf-8'))


def load_library():
    """Return independent copies of the bundled, licensed publisher records."""
    return deepcopy(_bundled())


def _safe_url(url):
    try:
        parsed = urlparse(url)
        return url if parsed.scheme in ('http','https') and parsed.hostname and not parsed.username else ''
    except (TypeError, ValueError):
        return ''


def _document(item, position):
    if not isinstance(item, dict):
        raise ValueError('每篇文献需要标题和正文。')
    title = item.get('title')
    body = item.get('text') or item.get('abstract')
    if not isinstance(title, str) or not title.strip() or not isinstance(body, str) or not body.strip():
        raise ValueError(f'第 {position + 1} 篇文献缺少标题或正文。')
    keywords = item.get('keywords') or ''
    if isinstance(keywords, list):
        keywords=' '.join(str(x) for x in keywords)
    return {'paper_id':str(item.get('paper_id') or item.get('paperId') or item.get('id') or position+1),
            'title':title.strip(), 'text':body, 'url':_safe_url(item.get('url','')),
            'year':item.get('year'), 'domain':item.get('field') or item.get('domain',''),
            'authors':item.get('authors') or [], 'license':_safe_url(item.get('license','')),
            'doi':item.get('doi',''), 'keywords':str(keywords)}


def _spans(body):
    # End at sentence boundaries; decimal values and versions remain together.
    start=0
    for match in re.finditer(r'[。！？](?:[”」』])?|[.!?](?:[”"])?(?=\s|$)|\n\s*\n',body):
        end=match.end()
        if body[start:end].strip():
            yield start,end
        start=end
    if body[start:].strip():
        yield start,len(body)


def _excerpt(row, question_terms):
    body=row['text']
    spans=list(_spans(body))
    sentences=[body[a:b] for a,b in spans]
    sentence_index=LexicalIndex(sentences, tokenizer=key_terms)
    scores=sentence_index.scores_for_terms(question_terms)
    best=max(range(len(sentences)), key=scores.__getitem__)
    keyword_only=scores[best]<=0
    budget=4000
    if keyword_only and len(body)<=budget:
        # The bilingual catalogue identifies a paper, not a particular sentence.
        # Methods/results/limitations can be anywhere in a short source abstract.
        start,end=0,len(body)
    elif keyword_only:
        # A long source cannot fit whole. Center a contiguous window on the
        # sentence most closely matching its own title, in the source language.
        title_scores=sentence_index.scores(row['title'])
        best=max(range(len(sentences)), key=title_scores.__getitem__)
        start=max(0, min(len(body)-budget,spans[best][0]-budget//3))
        end=start+budget
    else:
        first=max(0,best-1) if best==len(spans)-1 else best
        last=min(len(spans)-1,first+1)
        start,end=spans[first][0],spans[last][1]
        if end-start>budget:
            hit_start,hit_end=spans[best]
            if hit_end-hit_start>budget:
                # Scanned PDF tables may be one entire sentence. Rank overlapping
                # excerpts within the hit sentence instead of taking its prefix.
                starts=list(range(hit_start,hit_end-budget,budget//2))+[hit_end-budget]
                windows=(body[offset:offset+budget] for offset in starts)
                local=LexicalIndex(windows,tokenizer=key_terms).scores_for_terms(question_terms)
                start=starts[max(range(len(starts)),key=local.__getitem__)]
            else:
                start=max(start,min(end-budget,hit_start))
            end=start+budget
    while start<end and body[start].isspace():
        start+=1
    while end>start and body[end-1].isspace():
        end-=1
    return {'quote':body[start:end], 'start':start, 'end':end,
            'match_basis':'title_or_keywords' if keyword_only else 'passage'}


def search_library(question, papers=None, limit=5):
    """Search supplied title/text records or the bundled CC BY abstracts. Offsets are Python characters."""
    if not isinstance(question,str) or not question.strip():
        raise ValueError('请填写想在文献中查找的问题。')
    if isinstance(limit,bool) or not isinstance(limit,int) or not 1<=limit<=50:
        raise ValueError('显示篇数必须在 1 至 50 之间。')
    source = _bundled() if papers is None else papers
    if not isinstance(source,list):
        raise ValueError('文献库必须是文献列表。')
    rows=[_document(item,i) for i,item in enumerate(source)]
    query_terms=key_terms(question)
    documents=[row['title']+' '+row['title']+' '+row['keywords']+' '+row['text'] for row in rows]
    scores=LexicalIndex(documents, tokenizer=key_terms).scores_for_terms(query_terms)
    seen=set()
    matches=[]
    for idx in sorted(range(len(rows)), key=scores.__getitem__, reverse=True):
        row=rows[idx]
        if scores[idx]<=0:
            break
        if row['paper_id'] in seen:
            continue
        seen.add(row['paper_id'])
        matches.append({k:v for k,v in row.items() if k not in ('text','keywords')} |
                       _excerpt(row,query_terms) | {'score':round(scores[idx],6)})
        if len(matches)==limit:
            break
    return {'question':question.strip(), 'total':len(rows), 'items':matches, 'mode':'local-excerpts'}
