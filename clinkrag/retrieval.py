"""Dependency-free lexical and rank fusion signals for heterogeneous literature.

These signals reorder retrieved abstracts; they never replace source relevance review.
"""
from collections import Counter, defaultdict
import math
import re
import unicodedata


def search_query(value):
    # Semantic Scholar's relevance search requires hyphenated terms as separate words.
    return ' '.join(re.sub(r'[-\u2010-\u2014]', ' ', unicodedata.normalize('NFKC', value)).split())


def query_key(value):
    return search_query(value).casefold()


def terms(text):
    """Keep technical identifiers and support unsegmented CJK without a dictionary."""
    text = unicodedata.normalize('NFKC', str(text)).casefold()
    result = []
    for token in re.findall(r'[^\W_]+', text, flags=re.UNICODE):
        for part in re.findall(r'[\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]+|[^\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]+', token):
            if re.match(r'[\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]', part):
                result.extend(part)
                result.extend(part[i:i+2] for i in range(len(part)-1))
            else:
                result.append(part)
    return result


def clean_queries(value, maximum=2):
    if not isinstance(value, list) or maximum <= 0:
        return []
    result, seen = [], set()
    for query in value:
        if not isinstance(query, str):
            continue
        query = ' '.join(query.split())
        key = unicodedata.normalize('NFKC', query).casefold()
        if not 2 <= len(query) <= 300 or not terms(query) or key in seen:
            continue
        result.append(query)
        seen.add(key)
        if len(result) >= maximum:
            break
    return result


def lexical_scores(query, documents, k1=1.2, b=0.75):
    """BM25 over the fetched title+abstract corpus (not a full-library index)."""
    counts = [Counter(terms(text)) for text in documents]
    if not counts:
        return []
    frequency = Counter(term for row in counts for term in row)
    lengths = [sum(row.values()) for row in counts]
    average = sum(lengths) / len(counts) or 1
    query_terms = set(terms(query))
    scores = []
    for row, length in zip(counts, lengths):
        score = 0.0
        for term in query_terms & row.keys():
            idf = math.log(1 + (len(counts)-frequency[term]+0.5)/(frequency[term]+0.5))
            tf = row[term]
            score += idf * tf * (k1+1) / (tf + k1*(1-b+b*length/average))
        scores.append(score)
    return scores


def _ranks(scores):
    # Stable ties retain the semantic order rather than using arbitrary identifiers.
    return {pid: i+1 for i, (pid, _) in enumerate(sorted(scores.items(), key=lambda item: -item[1]))}


def fuse_rankings(question, semantic_ranked, plan, query_dimensions=None):
    """Weighted RRF: semantic 2, lexical 1, search-service 1; k=60.

    Query variants first share their topic/direction's weight. Each signal then
    contributes one ranking, so more query rewrites cannot add unbounded weight.
    Raw reranker scores stay in `score` for existing consumers.
    """
    if not semantic_ranked:
        return []
    query_dimensions = query_dimensions or {}
    papers = list({p['paperId']: p for p in semantic_ranked}.values())
    ids = [p['paperId'] for p in papers]
    documents = [(p.get('title') or '')+'\n'+(p.get('abstract') or '') for p in papers]
    queries = clean_queries([question]+list(plan.get('topic_queries', [])), maximum=3)
    lexical = defaultdict(float)
    for query in queries:
        scores = lexical_scores(query, documents)
        for pid, rank in _ranks({pid: score for pid, score in zip(ids, scores) if score > 0}).items():
            lexical[pid] += 1 / ((60+rank)*len(queries))
    lexical_ranks = _ranks(lexical)

    defaults = {q: 'topic' for q in plan.get('topic_queries', [])}
    for direction in plan.get('dimensions', []):
        for key in ('query', 'followup_query'):
            if direction.get(key):
                defaults.setdefault(direction[key], direction['id'])
    defaults.update(query_dimensions)
    defaults = {query_key(q): group for q, group in defaults.items()}
    grouped_queries, source_rows = defaultdict(set), {}
    for paper in papers:
        row = {}
        for query, rank in paper.get('query_ranks', {}).items():
            if not isinstance(rank, int) or isinstance(rank, bool) or rank < 1:
                continue
            key = query_key(query)
            group = defaults.get(key, 'other')
            grouped_queries[group].add(key)
            row[(group, key)] = min(rank, row.get((group, key), rank))
        source_rows[paper['paperId']] = row
    source_scores = {}
    for pid, row in source_rows.items():
        if row:
            source_scores[pid] = sum(1 / ((60+rank)*len(grouped_queries[group]))
                                     for (group, _), rank in row.items())
    source_ranks = _ranks(source_scores)
    result = []
    for semantic_rank, paper in enumerate(papers, 1):
        pid = paper['paperId']
        lexical_rank, source_rank = lexical_ranks.get(pid), source_ranks.get(pid)
        fusion = 2/(60+semantic_rank)
        fusion += 1/(60+lexical_rank) if lexical_rank else 0
        fusion += 1/(60+source_rank) if source_rank else 0
        result.append({**paper, 'fusion_score': fusion, 'ranking': {
            'semantic_rank': semantic_rank, 'lexical_rank': lexical_rank,
            'search_rank': source_rank, 'method': 'weighted-rrf', 'k': 60}})
    return sorted(result, key=lambda p: -p['fusion_score'])


def assessment_pool(ranked, plan, budget, query_dimensions=None):
    """Bound review cost, reserve global relevance, then rotate through directions."""
    budget = max(0, int(budget))
    if not budget:
        return []
    ranked = list({p['paperId']: p for p in ranked}.values())
    pool = list(ranked[:max(1, budget//2)])[:budget]
    used = {p['paperId'] for p in pool}
    query_dimensions = query_dimensions or {}
    groups = [set(plan.get('topic_queries', []))]
    for direction in plan.get('dimensions', []):
        groups.append({direction.get('query'), direction.get('followup_query')} |
                      {q for q, d in query_dimensions.items() if d == direction['id']})
    groups = [{query_key(q) for q in group if q} for group in groups]
    queues = [[p for p in ranked if group.intersection(query_key(q) for q in p.get('queries', []))] for group in groups]
    while len(pool) < budget:
        changed = False
        for queue in queues:
            while queue and queue[0]['paperId'] in used:
                queue.pop(0)
            if queue and len(pool) < budget:
                paper = queue.pop(0)
                pool.append(paper); used.add(paper['paperId']); changed = True
        if not changed:
            break
    for paper in ranked:
        if len(pool) >= budget:
            break
        if paper['paperId'] not in used:
            pool.append(paper); used.add(paper['paperId'])
    return pool
