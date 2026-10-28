"""JSONL tracing of the real pipeline, without logging authentication headers."""
import contextvars
import functools
import inspect
import json
import math
import re
import threading
import time
import traceback
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone


def plain(value):
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if hasattr(value, 'node'):
        return {'node': plain(value.node), 'references': plain(value.references),
                'child_queries': [c.node['query'] for c in value.children]}
    if hasattr(value, 'tolist'):
        return plain(value.tolist())
    return str(value)


class Recorder:
    def __init__(self, path, secrets=()):
        self.path = path
        self.secrets = [str(v) for v in secrets if v]
        self.lock = threading.Lock()
        self.parent = contextvars.ContextVar('trace_parent', default=None)
        self.root = None
        self.sequence = 0
        if self.path.exists():
            for line in self.path.read_text(encoding='utf-8').splitlines():
                try:
                    self.sequence = max(self.sequence, json.loads(line).get('seq', 0))
                except json.JSONDecodeError:
                    pass

    def clean(self, value):
        def scrub(obj):
            if isinstance(obj, dict):
                return {k: ('[REDACTED]' if re.search(r'api.?key|authorization|secret|access.?token', k, re.I)
                            else scrub(v)) for k, v in obj.items()}
            if isinstance(obj, list):
                return [scrub(v) for v in obj]
            if isinstance(obj, str):
                for secret in self.secrets:
                    obj = obj.replace(secret, '[REDACTED]')
            return obj
        return scrub(plain(value))

    def emit(self, **event):
        with self.lock:
            self.sequence += 1
            event.update(seq=self.sequence, time=datetime.now(timezone.utc).isoformat())
            with self.path.open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(self.clean(event), ensure_ascii=False, allow_nan=False) + '\n')

    @contextmanager
    def step(self, name, kind='stage', inputs=None):
        identity = uuid.uuid4().hex[:12]
        started = time.monotonic()
        self.emit(event='start', id=identity, parent=self.parent.get() or self.root,
                  name=name, kind=kind, input=inputs)
        token = self.parent.set(identity)
        result = {}
        try:
            yield result
        except Exception as exc:
            self.emit(event='end', id=identity, status='error', elapsed=time.monotonic()-started,
                      error=str(exc), traceback=traceback.format_exc())
            raise
        else:
            self.emit(event='end', id=identity, status='success', elapsed=time.monotonic()-started,
                      output=result.get('output'))
        finally:
            self.parent.reset(token)

    def wrap(self, function, name, kind='stage', root=False):
        signature = inspect.signature(function)
        @functools.wraps(function)
        def wrapped(*args, **kwargs):
            bound = signature.bind(*args, **kwargs)
            inputs = {k: plain(v) for k, v in bound.arguments.items() if k != 'self'}
            with self.step(name, kind, inputs) as step:
                if root:
                    self.root = self.parent.get()
                result = function(*args, **kwargs)
                step['output'] = plain(result)
                return result
        return wrapped


def instrument(recorder, pipe, search):
    stages = {
        'run': '02 · SciRAG 主流程',
        'gen_outline': '回答提纲', 'initial_result': '初始回答',
        'initial_critic': '知识缺口检查 / 生成子问题',
        'gap_critic': '子问题检索与解答',
        'additional_references_expansion': '候选资料检索、扩展与筛选',
        'symbolic_reason_rerank': '三步论文关系推理与筛选',
        'additional_result': '生成子问题回答',
        'bottom_up_aggregate': '自底向上汇总答案与来源',
        'reflective_refine': '反思与修改',
        'insert_attributions_posthoc_paragraph_all': '逐段引用归因',
    }
    for method, name in stages.items():
        setattr(pipe.pipeline, method, recorder.wrap(getattr(pipe.pipeline, method), name, root=method=='run'))
    search.search_snippet_via_query_w_citation_expansion = recorder.wrap(
        search.search_snippet_via_query_w_citation_expansion, 'Semantic Scholar 片段检索与引文扩展', 'retrieval')
    pipe.search_snippet_via_query_w_citation_expansion = search.search_snippet_via_query_w_citation_expansion

    factory = pipe.get_model
    class TracedModel:
        def __init__(self, model):
            self.model = model
        def chat(self, *args, **kwargs):
            return recorder.wrap(self.model.chat, '模型调用 · 提示词与响应', 'llm')(*args, **kwargs)
    def get_model(*args, **kwargs):
        return TracedModel(factory(*args, **kwargs))
    pipe.get_model = search.get_model = get_model

    original_reranker = pipe.create_reranker
    class TracedReranker:
        def __init__(self, *args, **kwargs):
            from llms.reranking import options
            with recorder.step('加载重排模型', 'gpu', options()) as step:
                self.model = original_reranker(*args, **kwargs)
                step['output'] = {'device': str(self.model.model.device)}
        def compute_score(self, pairs, **kwargs):
            with recorder.step('重排模型 · 候选相关性评分', 'gpu', {'pairs': pairs, **kwargs}) as step:
                result = self.model.compute_score(pairs, **kwargs)
                scores = [result] if isinstance(result, (int, float)) else result
                step['output'] = {'device': str(self.model.model.device), 'ranked': sorted(
                    [{'candidate': pair[1], 'score': float(score)} for pair, score in zip(pairs, scores)],
                    key=lambda row: row['score'], reverse=True)}
                return result
    pipe.create_reranker = TracedReranker

    # Capture individual HTTP attempts, including transport retries. Never record headers.
    import requests
    original_send = requests.sessions.Session.send
    def send(session, request, **kwargs):
        if not request.url.startswith('https://api.semanticscholar.org/'):
            return original_send(session, request, **kwargs)
        from urllib.parse import urlsplit, parse_qs
        parsed = urlsplit(request.url)
        body = request.body.decode('utf-8', errors='replace') if isinstance(request.body, bytes) else request.body
        with recorder.step('S2 请求 · ' + parsed.path.rsplit('/', 1)[-1], 'http',
                           {'method': request.method, 'path': parsed.path, 'query': parse_qs(parsed.query), 'body': body}) as step:
            response = original_send(session, request, **kwargs)
            try:
                data = response.json()
            except ValueError:
                data = response.text[:3000]
            step['output'] = {'http_status': response.status_code, 'retry_after': response.headers.get('Retry-After'), 'body': data}
            return response
    requests.sessions.Session.send = send
