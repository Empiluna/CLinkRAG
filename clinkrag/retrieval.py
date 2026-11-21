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


class LexicalIndex:
    """Build BM25 postings once for all queries on the same set of texts."""

    def __init__(self, documents, tokenizer=terms, k1=1.2, b=0.75):
        self.tokenizer = tokenizer
        self.postings = defaultdict(list)
        lengths = []
        for index, text in enumerate(documents):
            counts = Counter(tokenizer(text))
            lengths.append(sum(counts.values()))
            for term, count in counts.items():
                self.postings[term].append((index, count))
        self.size = len(lengths)
        average = sum(lengths) / max(1, self.size) or 1
        self.normalizers = [k1*(1-b+b*length/average) for length in lengths]
        self.k1 = k1

    def scores_for_terms(self, tokens):
        scores = [0.0] * self.size
        for token in sorted(set(tokens)):
            postings = self.postings.get(token)
            if not postings:
                continue
            matches = len(postings)
            idf = math.log(1 + (self.size-matches+0.5)/(matches+0.5))
            for index, count in postings:
                scores[index] += idf * count*(self.k1+1)/(count+self.normalizers[index])
        return scores

    def scores(self, query):
        return self.scores_for_terms(self.tokenizer(query))


def lexical_scores(query, documents, k1=1.2, b=0.75):
    return LexicalIndex(documents, k1=k1, b=b).scores(query)


def _ranks(scores):
    # Stable ties retain the semantic order rather than using arbitrary identifiers.
    return {pid: i+1 for i, (pid, _) in enumerate(sorted(scores.items(), key=lambda item: -item[1]))}


_QUERY_BOILERPLATE = frozenset("""
a an the these those this that it its to for in by on and are be been based between given is which
from more we can our or with of such some how what was as were at also through however their them
under use used using paper study papers approach method work methods results show propose address proposed
""".split())
_SENTENCE_BOUNDARY = re.compile(r'(?<=[.!?])\s+|(?<=[。！？])')
_BROAD_EVIDENCE = re.compile(
    r'\b(?:overview|summari[sz]e|synthesi[sz]e|systematic review|trade[- ]offs?|limitations|'
    r'multiple (?:criteria|dimensions|conditions)|(?:meet|satisfy) (?:all|both|the following)|'
    r'(?:both|as well as)\b.{0,80}\b(?:cost|accuracy|performance)|'
    r'(?:report|compare|assess|evaluate)\b.{0,50}\b(?:outcomes|performance|results|costs?))\b'
    r'|综述|汇总|归纳|综合比较|权衡|局限|多(?:维度|条件|项要求)|同时(?:满足|比较|考虑|给出)|'
    r'同时.{0,18}(?:成本|准确率|数据集|结果)|(?:比较|分析|报告|整理).{0,24}(?:效果|结果|成本|准确率|性能)', re.I)
_SIMILAR_METHOD = re.compile(
    r'\b(?:same|similar|analogous|comparable|equivalent)\s+(?:experimental\s+|research\s+|computational\s+)?'
    r'(?:method(?:s|ology)?|approach(?:es)?|designs?|procedures?|algorithms?|techniques?|protocols?)\b'
    r'|(?:相同|相似|类似|同类|一致)的?(?:实验|研究|计算)?(?:方法|设计|流程|算法|技术|方案)'
    r'|(?:实验设计|研究方法|技术路线|算法流程)(?:与.{0,12})?(?:相同|相似|类似)', re.I)
_REQUEST_EXAMPLES = re.compile(
    r'\b(?:which|find|identify|retrieve|locate|seek|looking for|are there|recommend|search)\b'
    r'|查找|寻找|检索|找出|哪些|有没有|推荐|请找|还有哪', re.I)
_PAPER_ACTION = re.compile(
    r'\b(?:we|this (?:paper|study)) (?:propos|introduc|construct|develop|implement|adapt|combin|'
    r'build|train|appl|use|estim|design)\w*\b|(?:我们|本文|本研究)(?:提出|建立|构建|开发|实现|设计|采用|训练|引入)', re.I)
_PROCEDURE_DETAIL = re.compile(
    r'\b(?:using|based on|by \w+ing|trained|algorithm|procedure|pipeline|protocol|estimator)\b'
    r'|(?:基于|通过|利用|首先|随后|算法|训练|抽样)', re.I)
_OUTCOME_CLAIM = re.compile(
    r'\b(?:we (?:find|show|demonstrate)|results? (?:show|suggest|indicate|demonstrate)|outperform\w*)\b'
    r'|(?:结果表明|结果显示|实验表明|显著优于|我们发现)', re.I)
_REFERENCE_SPLIT = re.compile(
    r'\n+|\b(?:abstract|reference excerpt|methods? excerpt)\s*[:：]|'
    r'(?:参考摘要|摘要|方法节选)\s*[:：]', re.I)
_REFERENCE_CONTEXT = re.compile(
    r'\b(?:however|in contrast|prior work|previous (?:work|studies)|existing (?:work|methods?|approaches?)|'
    r'(?:compared|in comparison) (?:to|with)|experimental evaluation|our experiments|'
    r'(?:experiments?|evaluations?) (?:show|demonstrate|indicate)|state.of.the.art performance)\b'
    r'|然而|以往研究|已有研究|现有(?:方法|研究)|相比|实验(?:结果|评估)|我们(?:比较了|评估了)', re.I)
_PROTOCOL_STEP = re.compile(
    r'(?:^|[.!?;]\s+)(?:first[, ]+|then[, ]+|next[, ]+)?'
    r'(?:sample|draw|fit|apply|estimate|construct|compute|train|repeat|measure)\b'
    r'|(?:^|[。；])(?:首先|随后|然后|计算|估计|采样|训练|拟合|重复)', re.I)


def _reference_needs_document(question):
    # Keep the researcher's instruction separate from pasted source material.
    # A full abstract may describe prior work, the method and results across
    # different sentences. Only a clearly procedural excerpt can act as one cue.
    parts = [p.strip() for p in _REFERENCE_SPLIT.split(question.replace('\r\n','\n')) if p.strip()]
    if len(parts)<2:
        return False
    requests = [bool(_REQUEST_EXAMPLES.search(p) and _SIMILAR_METHOD.search(p)) for p in parts]
    source = ' '.join(p for p,is_request in zip(parts,requests) if not is_request)
    if not any(requests) or not source:
        return False
    procedural = _PROTOCOL_STEP.search(source) or (_PAPER_ACTION.search(source) and _PROCEDURE_DETAIL.search(source))
    return not procedural or bool(_REFERENCE_CONTEXT.search(source) or _OUTCOME_CLAIM.search(source))


def method_passage_intent(question):
    """Distinguish looking for one procedure from collecting evidence across a paper."""
    text = ' '.join(unicodedata.normalize('NFKC', question).split())
    if text.count('?')>1 or _BROAD_EVIDENCE.search(text):
        return False
    if _SIMILAR_METHOD.search(text) and _REQUEST_EXAMPLES.search(text):
        return not _reference_needs_document(question)
    # A standalone paper-style account can serve as a method example. A general
    # question, outcome claim, or request without a positive cue keeps full-paper matching.
    return bool('?' not in text and _PAPER_ACTION.search(text) and _PROCEDURE_DETAIL.search(text)
                and not _OUTCOME_CLAIM.search(text))


def _long_question_lexical(question, variants, papers):
    # Method details are often concentrated in a single sentence. Counting matching
    # words all over an abstract also rewards papers that only share its application.
    owners, passage_terms, document_terms = [], [], []
    for i, paper in enumerate(papers):
        combined_terms = []
        for passage in [paper.get('title'), *_SENTENCE_BOUNDARY.split(paper.get('abstract') or '')]:
            if passage and passage.strip():
                owners.append(i)
                tokens = terms(passage)
                passage_terms.append(tokens)
                if variants:
                    combined_terms.extend(tokens)
        if variants:
            document_terms.append(combined_terms)
    keywords = [t for t in terms(question) if t not in _QUERY_BOILERPLATE]
    best = [0.0] * len(papers)
    passage_index = LexicalIndex(passage_terms, tokenizer=lambda tokens: tokens)
    for owner, score in zip(owners, passage_index.scores_for_terms(keywords)):
        best[owner] = max(best[owner], score)
    signals = [best]
    if variants:
        full = LexicalIndex(document_terms, tokenizer=lambda tokens: tokens)
        signals.extend(full.scores_for_terms(terms(q)) for q in variants)
    combined = [0.0] * len(papers)
    for scores in signals:
        floor, ceiling = min(scores), max(scores)
        if ceiling > floor:
            for i, score in enumerate(scores):
                combined[i] += (score-floor)/(ceiling-floor)
    return {p['paperId']:score for p,score in zip(papers,combined) if score>0}


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
    # Outgoing query validation caps each search string at 300 characters.
    # Local ranking can also use the researcher's complete original question.
    queries = clean_queries([question]+list(plan.get('topic_queries', [])), maximum=3)
    long_question = len(' '.join(question.split())) > 300
    if long_question:
        queries = [question, *queries[:2]]
    match_passages = long_question and method_passage_intent(question)
    if match_passages:
        lexical = _long_question_lexical(question, queries[1:], papers)
    else:
        lexical = defaultdict(float)
        documents = [(p.get('title') or '')+'\n'+(p.get('abstract') or '') for p in papers]
        index = LexicalIndex(documents)
        for query in queries:
            scores = index.scores(query)
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
            'search_rank': source_rank, 'method': 'weighted-rrf', 'k': 60,
            'lexical_scope': 'best-passage-and-query-variants' if match_passages else 'document'}})
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
