"""Chinese query cues backed by the local CC-CEDICT gloss index (see data/CEDICT.md)."""
from collections import defaultdict
from bisect import bisect_left
from functools import lru_cache
import math
from pathlib import Path
import re
from typing import NamedTuple
from zipfile import ZipFile

DATA = Path(__file__).with_name('data')/'cedict-glosses.idx'
_HAN = re.compile(r'[\u3400-\u9fff]+')
_OTHER_SCRIPT = re.compile(r'[\u3040-\u30ff\uac00-\ud7af]')
_ZH_STOP = frozenset('哪些 什么 研究 论文 如何 怎么 怎样 可以 进行 是否 有无 有何 这种 一种 一个 一些 哪种 哪项 哪篇 '
                     '方法 通过 使用 采用 需要 介绍 提出 利用 工作 哪个 以及 其中 之间 下列 有没有 '
                     '问题 到底 讨论 做到 实现 完成 有关 从而 而且 还有 方面 不同 相关 对比 比较 '
                     '方式 作用 过程 结果 情况 关于 能否 为什么 当中 中的'.split())
_EN_STOP = frozenset('a an the to or of in for and with as by on one sb sth someone something '
                     'more into that which be is etc very another some not need come being way '
                     'method study research paper both each make large several particular'.split())


@lru_cache(maxsize=1)
def _subject_names():
    lines=DATA.with_name('technical-names.tsv').read_text(encoding='utf-8').splitlines()
    return dict(line.split('\t',1) for line in lines)


@lru_cache(maxsize=1)
def _dictionary():
    return ZipFile(DATA)


@lru_cache(maxsize=64)
def _block(page):
    dictionary = _dictionary()
    try:
        data = dictionary.read(str(page))
    except KeyError:
        return {}
    return dict(line.split('\t',1) for line in data.decode().splitlines())


def chinese_glosses(text):
    """Longest headword first. Keep each word's English senses as alternatives."""
    if _OTHER_SCRIPT.search(text):
        return {}
    runs = _HAN.findall(text)
    groups = {}
    for run in runs:
        i=0
        while i+1<len(run):
            page=_block(ord(run[i])>>7)
            for end in range(min(i+12,len(run)),i+1,-1):
                word=run[i:end]
                if word in _ZH_STOP:
                    break
                if word in page:
                    groups[word] = page[word].split('|')
                    break
            else:
                i += 1
                continue
            i=end
    # Domain glossaries supply whole compounds. Retain their constituent words
    # as alternatives in case the source uses a descriptive wording.
    subjects = _subject_names()
    for run in runs:
        for start in range(len(run)-1):
            for end in range(min(start+12,len(run)),start+1,-1):
                word = run[start:end]
                if word in subjects and word not in _ZH_STOP:
                    groups[word] = subjects[word].split('|')
                    break
    return groups


def query_units(text, headwords):
    """Map every recognized source phrase to the units it spans in the question."""
    spans = []
    for word in headwords:
        start = text.find(word)
        while start >= 0:
            spans.append((word,start,start+len(word)))
            start = text.find(word,start+1)
    boundaries = sorted({boundary for _,start,end in spans for boundary in (start,end)})
    units = {}
    masks = defaultdict(int)
    for word,start,end in spans:
        for i in range(bisect_left(boundaries,start),bisect_left(boundaries,end)):
            unit = text[boundaries[i]:boundaries[i+1]]
            masks[word] |= units.setdefault(unit,1<<len(units))
    return masks,len(units)


class GlossEvidence(NamedTuple):
    hits: list
    headwords: frozenset
    in_title: bool


@lru_cache(maxsize=4096)
def _inflections(word):
    # Generate regular English noun/verb forms at query time. Only actual corpus
    # spellings enter the ranking or excerpt selection.
    forms = {word}
    if len(word)<3:
        return forms
    stem = word[:-1] if word.endswith('e') else word
    forms.update((word+'s', stem+'ed', stem+'ing'))
    if word.endswith(('ss','sh','ch','x')):
        forms.add(word+'es')
    if word.endswith('y') and word[-2] not in 'aeiou':
        forms.update((word[:-1]+'ies',word[:-1]+'ied'))
    if word.endswith(('ix','ex')):
        forms.add(word[:-2]+'ices')
    if word.endswith('ate'):
        forms.add(stem+'ion')
    if re.search(r'[^aeiou][aeiou][bdgmnpt]$',word):
        forms.update((word+word[-1]+'ed',word+word[-1]+'ing'))
    forms.update(form+'s' for form in list(forms) if form.endswith('ing'))
    return forms


@lru_cache(maxsize=2048)
def _gloss_pattern(gloss):
    words = gloss.replace('-',' ').split()
    alternatives = ['(?:'+'|'.join(sorted(_inflections(word)))+')' for word in words]
    return re.compile(r'\b'+r'[\s-]+'.join(alternatives)+r'\b',re.I|re.ASCII)


def gloss_matches(index, groups, rows):
    """Sparse BM25 per sense; require all content words of a sense in one document."""
    words_seen = {}
    def matching_word(word):
        if word in words_seen:
            return words_seen[word]
        per_doc = {}
        for form in sorted(_inflections(word)):
            posting = index.postings.get(form)
            if not posting:
                continue
            idf = math.log((index.size+1)/(len(posting)+.5))
            for idx,count in posting:
                score = idf*count*(index.k1+1)/(count+index.normalizers[idx])
                if idx not in per_doc or score > per_doc[idx][0]:
                    per_doc[idx] = score,form
        words_seen[word] = per_doc
        return per_doc

    by_doc=defaultdict(list)
    title_matches=set()
    for headword,glosses in groups.items():
        best={}
        variants = [(priority,form) for priority,gloss in enumerate(glosses)
                    for form in ([gloss,gloss.replace('-','')] if '-' in gloss else [gloss])]
        for priority,gloss in variants:
            words = gloss.replace('-',' ').split()
            parts = [matching_word(w) for w in words if w not in _EN_STOP]
            if not parts or not all(parts):
                continue
            pattern = _gloss_pattern(gloss)
            for idx in min(parts,key=len):
                if not all(idx in part for part in parts):
                    continue
                hits = [part[idx] for part in parts]
                in_title = pattern.search(rows[idx]['title'])
                if len(words)>1 and not in_title and not any(pattern.search(rows[idx][field]) for field in ('keywords','text')):
                    continue
                score = sum(s for s,_ in hits)/math.sqrt(len(parts)*(1+priority))
                if in_title:
                    title_matches.add(idx)
                    score *= 2
                if idx not in best or score > best[idx][0]:
                    best[idx] = score, [w for _,w in hits]
        for idx,item in best.items():
            by_doc[idx].append((headword,*item))
    for idx, matches in by_doc.items():
        # A compound and its constituents should not triple-count the same
        # language-model phrase. Keep the strongest independent cues.
        kept=[]
        for name, score, forms in sorted(matches,key=lambda m:-m[1]):
            if not any((name in other or other in name) and set(forms).intersection(words)
                       for other, _,words in kept):
                kept.append((name,score,forms))
        by_doc[idx]=GlossEvidence([(score,forms) for _,score,forms in kept],
                                  frozenset(name for name,_,_ in matches), idx in title_matches)
    return by_doc
