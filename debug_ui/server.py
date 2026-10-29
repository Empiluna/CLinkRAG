"""Loopback-only local workbench; stdlib HTTP server, no extra dependencies."""
import argparse
import hashlib
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit, parse_qs
import uuid

ROOT = Path(__file__).resolve().parents[1]
STATIC = Path(__file__).resolve().parent / 'static'
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'longans'))
from llms.settings import load_settings, configured_key
from debug_ui.model_settings import SettingsStore, check_local
from debug_ui.model_catalog import ModelCatalog


class BadRequest(ValueError):
    pass


class MissingRun(FileNotFoundError):
    pass


def validate_request(data):
    if not isinstance(data, dict):
        raise BadRequest('请求必须是 JSON 对象。')
    question = data.get('question')
    if not isinstance(question, str) or not 5 <= len(question.strip()) <= 4000:
        raise BadRequest('请输入 5–4000 字的问题。')
    result = {'question': question.strip()}
    client_id = data.get('client_request_id')
    if client_id is not None:
        if not isinstance(client_id, str) or not re.fullmatch(r'[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}', client_id):
            raise BadRequest('无效提交编号。请重新打开研究窗口。')
        result['client_request_id'] = client_id
    method = data.get('method', 'scirag')
    if method not in ('scirag', 'clinkrag', 'scirag_fixed', 'clinkrag_online'):
        raise BadRequest('未知算法。请选择 SciRAG 或 CLinkRAG。')
    result['method'] = method
    for key, default, low, high in [('initial_papers', 3, 1, 8), ('max_tokens', 1800, 500, 12000)]:
        value = data.get(key, default)
        if type(value) is not int or not low <= value <= high:
            raise BadRequest(f'{key} 必须是 {low}–{high} 的整数。')
        result[key] = value
    if method == 'clinkrag_online':
        value = data.get('online_papers', 12)
        if type(value) is not int or not 3 <= value <= 30:
            raise BadRequest('online_papers 必须是 3–30 的整数。')
        result['online_papers'] = value
        dimensions = data.get('research_dimensions', [])
        if (not isinstance(dimensions, list) or len(dimensions) > 6 or
                any(not isinstance(d, str) or not 1 <= len(d.strip()) <= 100 for d in dimensions)):
            raise BadRequest('研究维度最多 6 个，每个 1–100 字。')
        if dimensions:
            result['research_dimensions'] = list(dict.fromkeys(d.strip() for d in dimensions))
    # Optional fields preserve old request identities and historical defaults.
    options = []
    if method in ('clinkrag', 'clinkrag_online'):
        options += [('context_tokens', 1500, 16000), ('answer_words', 0, 6000),
                    ('graph_hops', 0, 3), ('max_path', 1, 4)]
        if 'answer_format' in data:
            if data['answer_format'] not in ('auto', 'sections', 'comparison'):
                raise BadRequest('请选择有效的回答结构。')
            result['answer_format'] = data['answer_format']
    if method == 'clinkrag_online':
        options += [('dimension_sources', 1, 3), ('extra_queries', 0, 4)]
    for key, low, high in options:
        if key in data:
            if type(data[key]) is not int or not low <= data[key] <= high:
                raise BadRequest(f'{key} 必须是 {low}–{high} 的整数。')
            result[key] = data[key]
    return result


class Jobs:
    def __init__(self, root=None):
        self.root = root or ROOT/'results'/'web-runs'
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.processes = {}
        # Previous server processes cannot be supervised by this instance.
        for path in self.root.glob('*/state.json'):
            if self.read(path).get('status') == 'running':
                self.write(path, {'status': 'interrupted', 'error': '上次服务已停止，已保存研究进度。'})

    @staticmethod
    def read(path, default=None):
        try:
            return json.loads(path.read_text(encoding='utf-8'))
        except (FileNotFoundError, json.JSONDecodeError):
            return default if default is not None else {}

    @staticmethod
    def write(path, data):
        temp = path.with_suffix('.server-tmp')
        temp.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        os.replace(temp, path)

    def folder(self, identity, include_deleted=False):
        if not re.fullmatch(r'[a-f0-9]{32}', identity):
            raise BadRequest('无效任务 ID。')
        path = self.root/identity
        root = self.root.resolve()
        if path.is_symlink() or path.resolve() != root/identity:
            raise BadRequest('研究目录路径异常，无法操作。')
        if not path.is_dir():
            raise MissingRun(identity)
        if not include_deleted and ((path/'deleted.json').exists() or
                                    identity in self.read(self.root/'.deleted-receipts.json')):
            raise MissingRun(identity)
        return path

    def listing(self):
        with self.lock:
            rows=[]
            receipts=self.read(self.root/'.deleted-receipts.json')
            for path in self.root.iterdir():
                if not path.is_dir() or not re.fullmatch(r'[a-f0-9]{32}', path.name):
                    continue
                if (path/'deleted.json').exists() or path.name in receipts:
                    continue
                rows.append(self.state(path.name))
            return sorted(rows, key=lambda row: row.get('created_at', ''), reverse=True)

    def state(self, identity):
        path = self.folder(identity)
        state = self.read(path/'state.json')
        process = self.processes.get(identity)
        if process and process.poll() is not None and state.get('status') == 'running':
            state = {'status': 'error', 'error': f'工作进程异常退出（代码 {process.returncode}），请查看步骤或本地 worker.log。'}
            self.write(path/'state.json', state)
        return {**self.read(path/'request.json'), **state, 'id': identity}

    def create(self, data):
        request = validate_request(data)
        with self.lock:
            # A lost HTTP response must not create another paid research job on retry.
            if request.get('client_request_id'):
                submission_hash=hashlib.sha256(request['client_request_id'].encode()).hexdigest()
                if submission_hash in self.read(self.root/'.deleted-receipts.json').values():
                    raise BadRequest('这项提交对应的研究已永久删除，请新建研究。')
                for prior_path in self.root.glob('*/request.json'):
                    prior = self.read(prior_path)
                    if prior.get('client_request_id') == request['client_request_id']:
                        if (prior_path.parent/'deleted.json').exists():
                            raise BadRequest('这项研究已删除，请新建研究。')
                        if any(prior.get(key) != value for key, value in request.items()):
                            raise BadRequest('同一提交编号对应不同参数，请创建新的研究提交。')
                        return self.state(prior_path.parent.name)
            if any(self.state(identity).get('status') == 'running' for identity in self.processes):
                raise BadRequest('已有任务正在运行，请等待完成或先取消。')
            identity = uuid.uuid4().hex
            path = self.root/identity
            path.mkdir()
            request['created_at'] = datetime.now(timezone.utc).isoformat()
            self.write(path/'request.json', request)
            self.write(path/'state.json', {'status': 'running'})
            try:
                with (path/'worker.log').open('wb') as log:
                    self.processes[identity] = subprocess.Popen(
                        [sys.executable, str(ROOT/'debug_ui'/'worker.py'), str(path)], cwd=ROOT,
                        stdout=log, stderr=log, env={**os.environ, 'PYTHONUTF8': '1', 'PYTHONUNBUFFERED': '1'},
                        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            except Exception as exc:
                self.write(path/'state.json', {'status': 'error', 'error': type(exc).__name__})
                raise
            return self.state(identity)

    def cancel(self, identity):
        with self.lock:
            path = self.folder(identity)
            state = self.state(identity)
            if state.get('status') != 'running':
                return state
            process = self.processes.get(identity)
            if process and process.poll() is None:
                process.terminate()
                process.wait(timeout=10)
            self.write(path/'state.json', {'status': 'cancelled', 'error': '已停止研究，已完成的检索与分析进度已保存。'})
            return self.state(identity)

    def resume(self, identity):
        with self.lock:
            path = self.folder(identity)
            state = self.state(identity)
            if state.get('status') == 'running':
                return state  # Idempotent double click or lost response.
            if state.get('method') != 'clinkrag_online':
                raise BadRequest('目前仅在线 CLinkRAG 支持继续研究。')
            if state.get('status') not in ('error', 'cancelled', 'interrupted'):
                raise BadRequest('这项研究无需继续。')
            if any(p.poll() is None for p in self.processes.values()):
                raise BadRequest('已有研究进程运行中，请稍后继续或先停止。')
            history = self.read(path/'resume-history.json', [])
            history.append({'time': datetime.now(timezone.utc).isoformat(), 'previous_state': self.read(path/'state.json')})
            self.write(path/'resume-history.json', history)
            self.write(path/'state.json', {'status': 'running', 'resumed_at': history[-1]['time']})
            try:
                with (path/'worker.log').open('ab') as log:
                    self.processes[identity] = subprocess.Popen(
                        [sys.executable, str(ROOT/'debug_ui'/'worker.py'), str(path), '--resume'], cwd=ROOT,
                        stdout=log, stderr=log, env={**os.environ, 'PYTHONUTF8': '1', 'PYTHONUNBUFFERED': '1'},
                        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            except Exception as exc:
                self.write(path/'state.json', {'status': 'error', 'error': type(exc).__name__})
                raise
            return self.state(identity)

    def delete(self, identity):
        with self.lock:
            if not re.fullmatch(r'[a-f0-9]{32}', identity):
                raise BadRequest('无效任务 ID。')
            receipts=self.read(self.root/'.deleted-receipts.json')
            if identity in receipts and not (self.root/identity).exists():
                return {'id': identity, 'deleted': True, 'permanent': True}
            path=self.folder(identity, include_deleted=True)
            # Stop and reap the worker before removing any record files.
            if identity not in receipts and not (path/'deleted.json').exists() and self.state(identity).get('status') == 'running':
                self.cancel(identity)
            process=self.processes.get(identity)
            if process and process.poll() is None:
                process.terminate()
                process.wait(timeout=10)
            self.processes.pop(identity, None)
            submission=self.read(path/'request.json').get('client_request_id')
            if identity not in receipts:
                # Only an irreversible submission fingerprint remains, never question/results.
                receipts[identity]=hashlib.sha256(submission.encode()).hexdigest() if submission else ''
                self.write(self.root/'.deleted-receipts.json', receipts)
            # folder() verified the resolved target is this exact child of the run root.
            # Python's rmtree does not traverse directory junction contents on Windows.
            shutil.rmtree(path)
            return {'id': identity, 'deleted': True, 'permanent': True}

    def events(self, identity, after=0):
        path = self.folder(identity)/'events.jsonl'
        if not path.exists():
            return []
        result = []
        with path.open(encoding='utf-8') as stream:
            for line in stream:
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue  # Concurrent append may leave an incomplete final line.
                if event['seq'] > after:
                    result.append(event)
        return result

    def close(self):
        for identity in list(self.processes):
            self.cancel(identity)


def make_handler(jobs, token, settings_store=None):
    settings_store = settings_store or SettingsStore()
    model_catalog = ModelCatalog(settings_store.loader)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def respond(self, data, status=200, content_type='application/json; charset=utf-8', download=False):
            body = data if isinstance(data, bytes) else json.dumps(data, ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'")
            if download:
                self.send_header('Content-Disposition', 'attachment; filename="scirag-debug.json"')
            self.end_headers()
            self.wfile.write(body)

        def check_local(self):
            host = self.headers.get('Host', '')
            if host not in (f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'):
                raise PermissionError('仅允许本地访问。')

        def do_GET(self):
            try:
                self.check_local()
                parsed = urlsplit(self.path)
                path = parsed.path
                if path in ('/', '/app.js', '/style.css', '/graph.js', '/graph.css', '/workspace.css', '/observatory.css', '/theme.js', '/visual.js', '/favicon.svg', '/product.css', '/product.js', '/explorer.js', '/reader.js', '/marked.umd.js', '/settings.js', '/settings.css', '/journey.js', '/journey.css', '/run-options.js', '/polish.css'):
                    filename = 'index.html' if path == '/' else path[1:]
                    mime = 'text/html' if path == '/' else 'text/javascript' if path.endswith('.js') else 'text/css'
                    return self.respond((STATIC/filename).read_bytes(), content_type=mime+'; charset=utf-8')
                if path == '/api/config':
                    settings = load_settings()
                    return self.respond({'token': token, 'model': settings.get('MODEL_NAME'),
                        'capabilities': {'resume': True, 'delete': True, 'permanent_delete': True},
                        'device': settings.get('RERANKER_DEVICE'), 's2_configured': bool(settings.get('S2_API_KEY')),
                        'llm_configured': bool(configured_key(settings))})
                if path == '/api/settings':
                    return self.respond(settings_store.view())
                if path == '/api/runs':
                    return self.respond(jobs.listing())
                if path == '/api/comparison':
                    folder = ROOT/'results/clinkrag-comparison-20261008'
                    return self.respond({'rows':jobs.read(folder/'comparison.json',[]),
                        'manifest':jobs.read(folder/'manifest.json'),
                        'full_scirag':[jobs.read(folder/(q+'-scirag_full_fixed.json')) for q in ('q1','q2','q3')]})
                match = re.fullmatch(r'/api/runs/([a-f0-9]{32})(?:/(export|graph))?', path)
                if match:
                    identity, export = match.groups()
                    if export == 'graph':
                        from debug_ui.graph_view import load_view
                        folder = jobs.folder(identity)
                        return self.respond(load_view(ROOT, folder, jobs.read(folder/'result.json', None), jobs.events(identity)))
                    after = max(0, int(parse_qs(parsed.query).get('after', ['0'])[0]))
                    data = {'run': jobs.state(identity), 'events': jobs.events(identity, 0 if export else after),
                            'result': jobs.read(jobs.folder(identity)/'result.json', None)}
                    return self.respond(data, download=bool(export))
                raise FileNotFoundError(path)
            except PermissionError as exc:
                self.respond({'error': str(exc)}, 403)
            except (ValueError, BadRequest) as exc:
                self.respond({'error': str(exc)}, 400)
            except MissingRun:
                self.respond({'error': '这项研究不存在或已删除，请刷新历史列表。', 'code': 'run_not_found'}, 404)
            except FileNotFoundError:
                self.respond({'error': '未找到内容。'}, 404)

        def do_POST(self):
            try:
                self.check_local()
                if self.headers.get('X-SciRAG-Token') != token:
                    raise PermissionError('页面凭证已过期，请刷新后重试。')
                origin = self.headers.get('Origin')
                if origin and origin != 'http://' + self.headers['Host']:
                    raise PermissionError('不接受其他网站的请求。')
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 <= size <= 20000:
                    raise BadRequest('请求过大。')
                data = json.loads(self.rfile.read(size) or b'{}')
                if self.path == '/api/models':
                    if not isinstance(data, dict) or type(data.get('refresh', False)) is not bool:
                        raise BadRequest('无效的模型列表请求。')
                    config = settings_store.catalog_config(data['service']) if 'service' in data else None
                    return self.respond(model_catalog.list(refresh=data.get('refresh', False), config=config))
                if self.path == '/api/settings':
                    with jobs.lock:
                        if any(jobs.state(identity).get('status') == 'running' for identity in jobs.processes):
                            raise BadRequest('研究正在运行。为保证一次研究使用同一套模型配置，请完成或停止后再保存。')
                        return self.respond(settings_store.save(data))
                if self.path == '/api/settings/check':
                    if not isinstance(data, dict):
                        raise BadRequest('检查请求必须是对象。')
                    return self.respond(check_local(data.get('values')))
                if self.path == '/api/runs':
                    return self.respond(jobs.create(data), 201)
                match = re.fullmatch(r'/api/runs/([a-f0-9]{32})/cancel', self.path)
                if match:
                    return self.respond(jobs.cancel(match[1]))
                match = re.fullmatch(r'/api/runs/([a-f0-9]{32})/resume', self.path)
                if match:
                    return self.respond(jobs.resume(match[1]))
                match = re.fullmatch(r'/api/runs/([a-f0-9]{32})/delete', self.path)
                if match:
                    if not isinstance(data, dict) or data.get('confirm_permanent') is not True:
                        raise BadRequest('删除后无法恢复，请刷新页面并确认永久删除。')
                    return self.respond(jobs.delete(match[1]))
                return self.respond({'error': '本地服务不支持这个操作，请重新启动项目服务。', 'code': 'endpoint_not_found'}, 404)
            except PermissionError as exc:
                self.respond({'error': str(exc)}, 403)
            except (ValueError, BadRequest) as exc:
                self.respond({'error': str(exc)}, 400)
            except MissingRun:
                self.respond({'error': '这项研究不存在或已删除，请刷新历史列表。', 'code': 'run_not_found'}, 404)
            except FileNotFoundError:
                self.respond({'error': '启动研究所需的本地文件不存在，请检查 Python 环境和 worker.py。', 'code': 'worker_file_missing'}, 500)
            except Exception:
                self.respond({'error': '本地服务无法启动或操作任务，请检查终端。'}, 500)
    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    # Bind before constructing Jobs so a second launch cannot mark active runs interrupted.
    server = ThreadingHTTPServer(('127.0.0.1', args.port), BaseHTTPRequestHandler)
    jobs = Jobs()
    server.RequestHandlerClass = make_handler(jobs, secrets.token_urlsafe(32))
    print(f'SciRAG Workbench: http://127.0.0.1:{args.port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        jobs.close()
        server.server_close()


if __name__ == '__main__':
    main()
