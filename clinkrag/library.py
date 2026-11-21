"""Local, extractive literature search with verifiable offsets. Standard library only."""
from collections import Counter, defaultdict
from functools import lru_cache, partial
import json
import math
from copy import deepcopy
from pathlib import Path
import re
import unicodedata
from urllib.parse import urlparse

from .retrieval import LexicalIndex
from .paper_ids import paper_references, without_references
from .technical import concepts, identifiers
from .cross_language import chinese_glosses, gloss_matches, query_units

_STOP = set(('a an the in on of to as for at with by from or and how what which when can do does is '
             'are was were study paper research result results using related about across tell show '
             'influence affect evidence studies their these those some when why did be do compare '
             'there has have in this that according you please would could').split())
_CJK_RANGES = r'\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af'
_TOKENS = re.compile(f'([{_CJK_RANGES}]+)|([^\\W_{_CJK_RANGES}]+)')
_HAS_CJK = re.compile(f'[{_CJK_RANGES}]')
_WORDS = re.compile(r'[^\W_]+')
_STOP_CJK = set('如何 怎么 怎样 研究 论文 可以 影响 关系 什么 哪些 哪种 有关 是否 能否 为什么 帮助 问题 有何 之间 相关 判断 不同 有什'.split())
_DATA = Path(__file__).with_name('data')/'library.json'


def key_terms(text):
    text = unicodedata.normalize('NFKC', text).casefold()
    if text.isascii() or not _HAS_CJK.search(text):
        return [word for word in _WORDS.findall(text)
                if word not in _STOP and (len(word)>1 or word.isdigit() or not word.isascii())]
    result = []
    for cjk, word in _TOKENS.findall(text):
        if cjk:
            result.extend(bigram for bigram in (cjk[i:i+2] for i in range(len(cjk)-1))
                          if bigram not in _STOP_CJK)
        elif word not in _STOP and (len(word)>1 or word.isdigit() or not word.isascii()):
            result.append(word)
    return result


def _tags(text, topics=None, symbols=True):
    values = {'topic:' + topic for topic in concepts(text, topics)} if topics is None or topics else set()
    if symbols:
        values.update('symbol:' + name for name in identifiers(text))
    return values


def _passage_terms(text, topics=None, symbols=True):
    return key_terms(text) + list(_tags(text,topics,symbols))


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
            'authors':deepcopy(item.get('authors') or []), 'license':_safe_url(item.get('license','')),
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


def _sentence_index(body, tokenizer):
    spans = list(_spans(body))
    return spans, LexicalIndex((body[a:b] for a,b in spans), tokenizer=tokenizer)


def _excerpt(row, question_terms, indexed):
    body=row['text']
    spans,sentence_index=indexed
    scores=sentence_index.scores_for_terms(question_terms)
    best=max(range(len(spans)), key=scores.__getitem__)
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
        best=max(range(len(spans)), key=title_scores.__getitem__)
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
                local=LexicalIndex(windows,tokenizer=sentence_index.tokenizer).scores_for_terms(question_terms)
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


def _validate_search(question,limit):
    if not isinstance(question,str) or not question.strip():
        raise ValueError('请填写想在文献中查找的问题。')
    if isinstance(limit,bool) or not isinstance(limit,int) or not 1<=limit<=50:
        raise ValueError('显示篇数必须在 1 至 50 之间。')


def _query(question):
    refs = set(paper_references(question,allow_bare_arxiv=True))
    text = without_references(question,allow_bare_arxiv=True) if refs else question
    words = key_terms(text)
    topics, symbols = concepts(text), identifiers(text)
    # A descriptive passage can mention many technical names. Preserve the
    # full-text evidence ranking; boost title and vocabulary for focused lookups.
    focused = bool(_HAS_CJK.search(text) or (len(words)<=8 and not text.rstrip().endswith(('.', ';'))))
    return words, topics if focused else frozenset(), symbols if focused else frozenset(), refs


def _feature_row(row, topics=None, symbols=True):
    title = key_terms(row['title'])
    keywords = key_terms(row['keywords'])
    full = Counter(key_terms(row['text']))
    full.update(title)
    full.update(title)
    full.update(keywords)
    heading = row['title']+' '+row['keywords']
    return {'full':full,'heading':Counter(title+keywords),
            'heading_tags':sorted(_tags(heading,topics,symbols)),
            'body_tags':sorted(_tags(row['text'],topics,symbols))}


def library_features(papers):
    """Portable input statistics for a reviewed static corpus, in source order."""
    return [_feature_row(_document(paper,i)) for i,paper in enumerate(papers)]


def _zone_postings(fields):
    postings = defaultdict(dict)
    for i,(heading,body) in enumerate(fields):
        for tag in body:
            postings[tag][i] = 1
        for tag in heading:
            postings[tag][i] = postings[tag].get(i,0) + 2
    return dict(postings)


class LibraryIndex:
    """Index one snapshot. All returned passage offsets refer to the original input strings."""
    def __init__(self, papers, *, features=None, _query_terms=None):
        if not isinstance(papers,list):
            raise ValueError('文献库必须是文献列表。')
        rows = [_document(item, i) for i,item in enumerate(papers)]
        self.rows = rows
        topics, symbols = (None, True) if _query_terms is None else (_query_terms[1], bool(_query_terms[2]))
        defer_tags = features is None and _query_terms is None
        if features is None:
            features = [_feature_row(row,frozenset() if defer_tags else topics,False if defer_tags else symbols) for row in rows]
        if len(features) != len(rows):
            raise ValueError('词项记录数与文献数不一致。')
        # LexicalIndex accepts both token sequences and pre-counted mappings.
        self.full = LexicalIndex((r['full'] for r in features),tokenizer=lambda counts:counts)
        use_tags = topics is None or bool(topics) or symbols
        self.heading = (LexicalIndex((r['heading'] for r in features),tokenizer=lambda counts:counts)
                        if use_tags else None)
        if defer_tags:
            # The first query may concern another discipline. Extract technical
            # fields only when requested; source-derived statistics stay local.
            self.tag_postings = lru_cache(maxsize=1)(lambda: _zone_postings(
                (_tags(r['title']+' '+r['keywords']), _tags(r['text'])) for r in rows))
        else:
            postings = _zone_postings((f['heading_tags'],f['body_tags']) for f in features)
            self.tag_postings = lambda: postings
        self.references = defaultdict(list)
        if _query_terms is None or _query_terms[3]:
            for i,row in enumerate(rows):
                ids = paper_references(' '.join(str(row[k] or '') for k in ('doi','paper_id','url')),allow_bare_arxiv=True)
                for ref in ids:
                    self.references[ref].append(i)
        # This bounded cache belongs to the snapshot. No private source text is
        # stored in module-level caches, on disk, or retained between requests.
        tokenizer = partial(_passage_terms, topics=topics, symbols=symbols)
        self.sentences = lru_cache(maxsize=64)(lambda idx,technical: _sentence_index(rows[idx]['text'],tokenizer if technical else key_terms))

    def search(self, question, limit=5):
        _validate_search(question,limit)
        return self._search(question,limit,_query(question))

    def _search(self, question, limit, query):
        words,topics,symbols,refs = query
        tags = {'topic:'+topic for topic in topics} | {'symbol:'+symbol for symbol in symbols}
        scores = self.full.scores_for_terms(words)
        if tags:
            headings = self.heading.scores_for_terms(words)
            postings = self.tag_postings()
            for i,score in enumerate(headings):
                scores[i] += score
            for tag in sorted(tags):
                found = postings.get(tag,{})
                weight = math.log((len(self.rows)+1)/(len(found)+.5))
                for i,zone_weight in found.items():
                    scores[i] += zone_weight * weight
            # For a short named lookup, punctuation or a model version is part
            # of the name: "B+ tree" and "B tree" must stay distinguishable.
            if symbols and len(words)<=2:
                named_titles = {i for name in symbols for i,zone in postings.get('symbol:'+name,{}).items()
                                if zone>=2}
                boost = max(scores,default=0)+1
                for i in named_titles:
                    scores[i] += boost
        translated = {}
        if not refs and _HAS_CJK.search(question):
            groups = chinese_glosses(question)
            if groups:
                units, unit_count = query_units(question,groups)
                threshold = max(min(2,unit_count),math.ceil(.4*unit_count))
                for idx, evidence in gloss_matches(self.full, groups, self.rows).items():
                    matched = 0
                    for name in evidence.headwords:
                        matched |= units[name]
                    covered = matched.bit_count()
                    # Broad glosses such as "consensus" on their own cannot
                    # introduce a new paper for a multi-concept question.
                    if not scores[idx] and (covered<threshold or (covered<3 and not evidence.in_title)):
                        continue
                    scores[idx] += (covered/unit_count)*sum(score for score,_ in evidence.hits)
                    translated[idx] = [word for _,words in evidence.hits for word in words]
        if refs:
            # A cited DOI in someone else's abstract is not that paper's identity.
            boost = max(scores,default=0) + 1
            for i in {i for ref in refs for i in self.references.get(ref,())}:
                scores[i] += boost
        seen = set()
        matches = []
        for idx in sorted(range(len(self.rows)), key=scores.__getitem__, reverse=True):
            if scores[idx] <= 0:
                break
            row = self.rows[idx]
            if row['paper_id'] in seen:
                continue
            seen.add(row['paper_id'])
            metadata = {k:v for k,v in row.items() if k not in ('text','keywords')}
            excerpt_terms = words + sorted(tags)
            english_terms = translated.get(idx)
            if english_terms:
                # A Chinese catalogue label identifies a paper, not a particular
                # sentence. A broad gloss (e.g. 年代 → age) must not narrow a
                # catalogue-only match and hide the results later in its abstract.
                catalogue_terms = {t for t in key_terms(row['keywords']) if _HAS_CJK.search(t)}
                if catalogue_terms.isdisjoint(words):
                    excerpt_terms += english_terms
            matches.append(deepcopy(metadata) | _excerpt(row,excerpt_terms,self.sentences(idx,bool(tags))) |
                           {'score':round(scores[idx],6)})
            if len(matches) == limit:
                break
        return {'question':question.strip(),'total':len(self.rows),'items':matches,'mode':'local-excerpts'}


@lru_cache(maxsize=1)
def _bundled_index():
    return LibraryIndex(_bundled())


def search_library(question, papers=None, limit=5):
    """Search supplied title/text records or the bundled CC BY abstracts. Offsets are Python characters."""
    _validate_search(question,limit)
    query = _query(question)
    index = _bundled_index() if papers is None else LibraryIndex(papers,_query_terms=query)
    return index._search(question,limit,query)
