"""Bilingual computing terminology and exact identifiers used by local literature search."""
import re
import unicodedata
from functools import lru_cache

# Equivalences describe topics, not publications. Keep ambiguous short aliases out.
# The first spelling is the human-readable canonical English term.
_TOPICS = (
    ('large language model', 'llm', 'llms', 'large language models', '大语言模型', '大型语言模型'),
    ('retrieval augmented generation', 'rag', '检索增强生成', '检索增强式生成'),
    ('question answering', 'question answer system', '自动问答', '问答系统', '问答'),
    ('multi hop', 'multihop', '多跳'),
    ('information retrieval', '信息检索', '文献检索'),
    ('dense retrieval', 'dense retriever', 'dense retrievers', '稠密检索', '密集检索', '稠密向量检索'),
    ('hybrid search', 'hybrid retrieval', 'hybrid retriever', '混合检索', '混合搜索'),
    ('semantic search', '语义搜索', '语义检索'),
    ('document ranking', 'learning to rank', '文档排序', '学习排序', '排序学习'),
    ('reranking', 're ranking', 'reranker', 'rerankers', '重排序', '重排'),
    ('inverted index', 'inverted indexes', '倒排索引'),
    ('nearest neighbor', 'nearest neighbors', 'nearest neighbour', 'nearest neighbours', '近邻搜索', '最近邻', '近邻检索'),
    ('approximate nearest neighbor', 'approximate nearest neighbors', '近似最近邻'),
    ('natural language processing', 'nlp', '自然语言处理'),
    ('machine translation', 'neural machine translation', '机器翻译'),
    ('named entity recognition', '命名实体识别'),
    ('speech recognition', 'automatic speech recognition', '语音识别'),
    ('sentiment analysis', '情感分析'),
    ('language modeling', 'language modelling', '语言建模'),
    ('neural network', 'neural networks', '神经网络'),
    ('attention mechanism', 'attention mechanisms', 'attention', '注意力机制', '注意力'),
    ('self attention', '自注意力', '自注意'),
    ('mixture of experts', 'moe', '混合专家', '专家混合'),
    ('fine tuning', 'finetuning', 'finetune', '微调'),
    ('parameter efficient fine tuning', 'peft', '参数高效微调', '高效参数微调'),
    ('low rank adaptation', 'lora', '低秩适配', '低秩微调'),
    ('pretraining', 'pre training', 'pretrained', '预训练'),
    ('reinforcement learning', '强化学习', '增强学习'),
    ('reinforcement learning from human feedback', 'rlhf', '人类反馈强化学习'),
    ('preference optimization', 'preference optimisation', '偏好优化'),
    ('contrastive learning', '对比学习'),
    ('self supervised learning', 'self supervision', '自监督学习'),
    ('transfer learning', '迁移学习'),
    ('federated learning', '联邦学习'),
    ('in context learning', '上下文学习', '语境学习'),
    ('continual learning', 'lifelong learning', '持续学习', '终身学习'),
    ('few shot learning', 'few shot', '小样本学习', '少样本学习'),
    ('zero shot', '零样本'),
    ('knowledge distillation', 'model distillation', '知识蒸馏', '模型蒸馏'),
    ('model compression', '模型压缩'),
    ('quantization', 'quantisation', '量化'),
    ('gradient descent', '梯度下降'),
    ('backpropagation', 'back propagation', '反向传播'),
    ('graph neural network', 'graph neural networks', 'gnn', 'gnns', '图神经网络'),
    ('convolutional neural network', 'convolutional neural networks', 'cnn', 'cnns', '卷积神经网络'),
    ('diffusion model', 'diffusion models', '扩散模型'),
    ('generative adversarial network', 'generative adversarial networks', 'gan', 'gans', '生成对抗网络'),
    ('computer vision', '计算机视觉'),
    ('image classification', '图像分类'),
    ('object detection', '目标检测', '物体检测'),
    ('semantic segmentation', '语义分割'),
    ('image segmentation', '图像分割'),
    ('image generation', '图像生成'),
    ('multimodal', 'multi modal', '多模态'),
    ('vision language', '视觉语言'),
    ('knowledge graph', 'knowledge graphs', '知识图谱'),
    ('recommendation system', 'recommendation systems', 'recommender system', 'recommender systems', '推荐系统'),
    ('time series', '时间序列'),
    ('distributed system', 'distributed systems', '分布式系统'),
    ('distributed computing', 'distributed computation', '分布式计算'),
    ('parallel computing', 'parallel computation', '并行计算'),
    ('distributed training', '分布式训练'),
    ('data parallelism', 'data parallel', '数据并行'),
    ('model parallelism', 'model parallel', '模型并行'),
    ('operating system', 'operating systems', '操作系统'),
    ('garbage collection', '垃圾回收'),
    ('virtual memory', '虚拟内存'),
    ('memory management', '内存管理'),
    ('query optimization', 'query optimisation', 'query optimizer', 'query optimizers', 'query optimiser', 'query optimisers', 'query planning', '查询优化', '查询优化器', '查询规划'),
    ('join ordering', 'join order', '连接顺序', '连接排序'),
    ('database', 'databases', '数据库'),
    ('transaction isolation', '事务隔离'),
    ('concurrency control', '并发控制'),
    ('key value store', 'key value stores', '键值存储'),
    ('log structured merge tree', 'lsm tree', 'lsm trees', '日志结构合并树'),
    ('graph algorithm', 'graph algorithms', '图算法'),
    ('shortest path', 'shortest paths', '最短路径'),
    ('dynamic programming', '动态规划'),
    ('approximation algorithm', 'approximation algorithms', '近似算法'),
    ('computational complexity', '计算复杂性', '计算复杂度'),
    ('compiler', 'compilers', '编译器'),
    ('program analysis', '程序分析'),
    ('static analysis', '静态分析'),
    ('type inference', '类型推断'),
    ('type system', 'type systems', '类型系统'),
    ('formal verification', '形式化验证'),
    ('model checking', '模型检验', '模型检测'),
    ('differential privacy', '差分隐私'),
    ('fault tolerance', 'fault tolerant', '容错'),
    ('distributed consensus', 'consensus protocol', 'consensus protocols', 'consensus algorithm', 'consensus algorithms', 'consensus problem', '共识协议', '共识算法', '分布式共识', '分布式一致性协议'),
    ('computer architecture', '计算机体系结构', '计算机架构'),
    ('congestion control', '拥塞控制'),
    ('packet scheduling', '分组调度', '数据包调度')
)

_ZH = {}
_EN = {}
for _canonical, *_aliases in _TOPICS:
    for _alias in (_canonical, *_aliases):
        if _alias.isascii():
            _EN[_alias] = _canonical
        else:
            _ZH[_alias] = _canonical

# Keep short natural-language aliases on ASCII word boundaries even in mixed Chinese text.
_SYMBOL = re.compile(r'(?<![a-z0-9])(?:c\+\+(?:\d{2})?|[cf]#|\.net|b\s*\+\s*-?\s*trees?|objective[- ]c)(?![a-z0-9])', re.ASCII)
_VERSION = re.compile(r'(?<![a-z0-9])([a-z]+)[-_]?(\d+(?:\.\d+)*(?:[a-z]+)?)(?![a-z0-9])', re.ASCII)
_SPACED_VERSION = re.compile(r'(?<![A-Za-z0-9])([A-Z]{2,}[A-Za-z]*|[A-Z][a-z]+[A-Z][A-Za-z]*)[ \t]+(\d+(?:\.\d+)*(?:[a-z]+)?)(?![A-Za-z0-9])', re.ASCII)
_DIGIT = re.compile('[0-9]')
_NON_ASCII_HYPHEN = re.compile('[‐‑‒–—]')
_COMPUTING_CONTEXT = re.compile(r'\b(?:distributed|asynchronous|byzantine|fault tolerant)\b', re.ASCII)

# An occurrence of “graph neural networks” also contains “neural networks”.
# Preserve nested concepts in the reusable index and in a query-specific index.
_NESTED_EN = {}
for _phrase in _EN:
    _words = _phrase.split()
    _NESTED_EN[_phrase] = {_EN[part] for i in range(len(_words)) for j in range(i+1,len(_words)+1)
                           if (part := ' '.join(_words[i:j])) in _EN}
_NESTED_ZH = {s:{topic for alias,topic in _ZH.items() if alias in s} for s in _ZH}
_ATTENTION_CONTEXT = re.compile(r'transformers?|neural|encoder|decoder|attention mechanism|self.attention|multi.head|注意力机制|自注意|注意力头|神经网络|多头',re.IGNORECASE)
_LO_RANK_CONTEXT = re.compile(r'low.rank adapt|fine.tun|language model|neural|参数|低秩|微调|模型|适配器',re.IGNORECASE)


@lru_cache(maxsize=64)
def _patterns(only):
    en = [s for s in _EN if only is None or _EN[s] in only]
    zh = [s for s in _ZH if only is None or _ZH[s] in only]
    return (re.compile(r'\b(?:'+'|'.join(sorted(en,key=len,reverse=True))+r')\b', re.ASCII) if en else None,
            re.compile('|'.join(sorted(zh,key=len,reverse=True))) if zh else None)


def concepts(text, only=None):
    """Match canonical topics. One-shot searches can restrict work to the query's topics."""
    if only is not None and not only:
        return frozenset()
    text = unicodedata.normalize('NFKC', text)
    english,chinese = _patterns(only)
    found = set()
    if chinese and not text.isascii():
        for match in chinese.finditer(text):
            found.update(_NESTED_ZH[match.group()])
    words = ' '.join(text.casefold().replace('-',' ').replace('_',' ').split())
    if not words.isascii():
        words = _NON_ASCII_HYPHEN.sub(' ', words)
    if english:
        for match in english.finditer(words):
            found.update(_NESTED_EN[match.group()])
    if ((only is None or 'distributed consensus' in only) and 'consensus' in words
            and _COMPUTING_CONTEXT.search(words)):
        found.add('distributed consensus')
    if 'attention mechanism' in found and not _ATTENTION_CONTEXT.search(text):
        found.discard('attention mechanism')
    if ('low rank adaptation' in found and 'LoRA' not in text and 'LORA' not in text
            and text.strip().casefold() != 'lora' and not _LO_RANK_CONTEXT.search(text)):
        found.discard('low rank adaptation')  # LoRa radio networks use a different name.
    if ('retrieval augmented generation' in found and 'rag' in words and 'RAG' not in text
            and words.strip() != 'rag' and not any(t in words for t in ('retriev','generat','language model','检索增强'))):
        found.discard('retrieval augmented generation')
    return frozenset(found if only is None else found.intersection(only))


def identifiers(text):
    """Preserve significant symbols and version components in technical names."""
    original = unicodedata.normalize('NFKC', text)
    text = original.casefold()
    if not text.isascii():
        text = _NON_ASCII_HYPHEN.sub('-', text)
    exact = set()
    if '+' in text or '#' in text or '.net' in text or 'objective' in text:
        for match in _SYMBOL.finditer(text):
            compact = re.sub(r'[\s-]+', '', match.group())
            exact.add(compact[:-1] if compact == 'b+trees' else compact)
            if compact.startswith('c++'):
                exact.add('c++')
    if _DIGIT.search(text):
        exact.update(m[1]+m[2] for m in _VERSION.finditer(text))
        exact.update((m[1]+m[2]).casefold() for m in _SPACED_VERSION.finditer(original))
    return frozenset(exact)
