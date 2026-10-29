"""Deterministic corpus, co-occurrence, condition and path primitives."""
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
import re

VERSION = 'clinkrag-1.1'

def identity(value):
    return hashlib.sha256(str(value).encode()).hexdigest()[:20]

def normalized(value):
    return re.sub(r'\s+', ' ', str(value).casefold()).strip()

def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    temporary.replace(path)

@dataclass
class Config:
    seeds: int = 5
    hops: int = 2
    neighbors: int = 12
    max_candidates: int = 60
    max_path: int = 3
    beam: int = 20
    min_windows: int = 3
    min_papers: int = 2
    tau: float = 5.0
    context_tokens: int = 5000
    max_tokens: int = 1400
    associations: bool = True
    paths: bool = True
    conditions: bool = True
    answer_words: int = 0
    answer_format: str = 'auto'

    def to_dict(self):
        return asdict(self)

def prepare_corpus(papers):
    """Deduplicate by identity and text; keep original offsets for every window."""
    documents, passages, seen = [], [], set()
    for paper in papers:
        text = str(paper.get('text') or paper.get('abstract') or '').strip()
        pid = str(paper.get('paperId') or paper.get('id') or identity(text))
        if not text or pid in seen:
            continue
        seen.add(pid)
        documents.append({'id': pid, 'title': paper.get('title',''), 'text': text,
                          'url': paper.get('url') or 'https://www.semanticscholar.org/paper/'+pid,
                          'text_hash': identity(text)})
        seen_windows = set()
        # Nonoverlapping paragraphs/sentence groups, unlike overlapping retrieval chunks.
        for paragraph in re.finditer(r'\S[\s\S]*?(?=\n\s*\n|$)', text):
            start, end = paragraph.span()
            if end-start < 40:
                continue
            boundaries = [start]
            for sentence in re.finditer(r'(?<=[.!?])\s+|(?<=[。！？])\s*', text[start:end]):
                point = start+sentence.end()
                if point-boundaries[-1] >= 650:
                    boundaries.append(point)
            if boundaries[-1] != end:
                boundaries.append(end)
            for a,b in zip(boundaries, boundaries[1:]):
                chunk = text[a:b].strip()
                a += len(text[a:b])-len(text[a:b].lstrip())
                b = a+len(chunk)
                signature = normalized(chunk)
                if len(chunk)<40 or signature in seen_windows:
                    continue
                seen_windows.add(signature)
                passages.append({'id': identity(pid+':'+str(a)), 'paper_id': pid,
                    'title': paper.get('title',''), 'text': chunk, 'start': a, 'end': b})
    if not passages:
        raise ValueError('No usable corpus text.')
    version = identity(json.dumps(documents, ensure_ascii=False, sort_keys=True))
    return {'version': version, 'papers': documents, 'passages': passages}

def locate(quote, text):
    """Allow whitespace variation only; never accept paraphrases as quotations."""
    if not isinstance(quote,str) or len(quote.strip())<12:
        return None
    pattern = r'\s+'.join(re.escape(word) for word in quote.split())
    match = re.search(pattern,text)
    return {'quote': match.group(), 'start':match.start(), 'end':match.end()} if match else None

def association_stats(passages, mentions, config):
    by_window=defaultdict(set)
    for mention in mentions:
        by_window[mention['passage_id']].add(mention['entity_id'])
    singles, pairs, documents = Counter(),Counter(),defaultdict(set)
    for passage in passages:
        entities=sorted(by_window[passage['id']])
        singles.update(entities)
        for i,left in enumerate(entities):
            for right in entities[i+1:]:
                key=(left,right)
                pairs[key]+=1
                documents[key].add(passage['paper_id'])
    N=len(passages)
    edges=[]
    for (left,right), count in sorted(pairs.items()):
        p=count/N
        npmi=0.0 if p>=1 else math.log(count*N/(singles[left]*singles[right]))/-math.log(p)
        score=max(0,npmi)*count/(count+config.tau)
        edges.append({'source':left,'target':right,'type':'co_occurs','directed':False,
            'N':N,'ci':singles[left],'cj':singles[right],'cij':count,
            'paper_count':len(documents[(left,right)]),'npmi':npmi,'score':score,
            'eligible':count>=config.min_windows and len(documents[(left,right)])>=config.min_papers and score>0})
    return {'N':N,'single_counts':dict(singles),'edges':edges}

CONDITION_KEYS=('task','model','dataset','metric','setting','population','period','method','assumptions')
UNKNOWN={'','unknown','unspecified','not stated','none','null','general'}

def compatible(a,b):
    conflicts=[]; matches=[]; missing=[]
    # Include any additional explicit scope instead of silently ignoring a new field.
    for key in dict.fromkeys((*CONDITION_KEYS, *a.keys(), *b.keys())):
        left=normalized(a.get(key,'unknown'));right=normalized(b.get(key,'unknown'))
        if left in UNKNOWN or right in UNKNOWN:
            missing.append(key)
        elif left==right:
            matches.append(key)
        else:
            conflicts.append({'field':key,'left':left,'right':right})
    # Similarity is not enough to establish compatible experiments. Unknown stays unknown.
    state='conflict' if conflicts else 'compatible' if not missing else 'unknown'
    return {'state':state,'matches':matches,'missing':missing,'conflicts':conflicts}

def build_paths(claims, ranks, config):
    """Keep causal direction; association edges never occur in explanation paths."""
    supported=[c for c in claims if c['type']=='reported_causal' and c.get('verified')]
    queue=[{'claims':[c],'checks':[]} for c in supported]
    paths=[]; rejected=[]
    def scoring(item):
        chain=item['claims']
        relevance=sum(ranks.get(c['passage_id'],0) for c in chain)/len(chain)
        papers=len({c['paper_id'] for c in chain})
        uncertain=sum(x['state']=='unknown' for x in item['checks'])
        return relevance+0.15*min(2,papers-1)-0.2*uncertain-0.04*(len(chain)-1)
    for _ in range(config.max_path):
        next_queue=[]
        for item in sorted(queue,key=scoring,reverse=True)[:config.beam]:
            chain=item['claims']; score=scoring(item)
            paths.append({'id':identity('|'.join(c['id'] for c in chain)),
                'claim_ids':[c['id'] for c in chain], 'passage_ids':list(dict.fromkeys(c['passage_id'] for c in chain)),
                'paper_ids':list(dict.fromkeys(c['paper_id'] for c in chain)),
                'checks':item['checks'],'score':score,
                'state':'uncertain' if any(x['state']=='unknown' for x in item['checks']) else 'supported',
                'score_components':{'mean_relevance':sum(ranks.get(c['passage_id'],0) for c in chain)/len(chain),
                    'source_bonus':0.15*min(2,len({c['paper_id'] for c in chain})-1),
                    'unknown_penalty':0.2*sum(x['state']=='unknown' for x in item['checks']),
                    'length_penalty':0.04*(len(chain)-1)}})
            used={c['source'] for c in chain}|{c['target'] for c in chain}
            for candidate in supported:
                if candidate['source']!=chain[-1]['target'] or candidate['target'] in used:
                    continue
                check=compatible(chain[-1].get('conditions',{}),candidate.get('conditions',{}))
                previous=chain[-1].get('target_state','unspecified')
                following=candidate.get('source_state','unspecified')
                if previous!='unspecified' and following!='unspecified' and previous!=following:
                    check['state']='conflict'
                    check['conflicts'].append({'field':'bridge_state','left':previous,'right':following})
                elif previous=='unspecified' or following=='unspecified':
                    if check['state']=='compatible':check['state']='unknown'
                    check['missing'].append('bridge_state')
                check.update(left=chain[-1]['id'],right=candidate['id'])
                if config.conditions and check['state']=='conflict':
                    rejected.append(check)
                    continue
                next_queue.append({'claims':chain+[candidate],'checks':item['checks']+[check]})
        queue=next_queue
        if not queue:
            break
    unique={p['id']:p for p in paths}
    return sorted(unique.values(),key=lambda p:p['score'],reverse=True),rejected

def citation_audit(answer, source_count):
    indexes=[int(i) for i in re.findall(r'\[(\d+)\]',answer)]
    return {'indices':sorted(set(indexes)), 'invalid':sorted({i for i in indexes if i>=source_count}),
            'has_citations':bool(indexes), 'semantic_support_verified':False}
