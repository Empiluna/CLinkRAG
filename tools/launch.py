"""Open one Windows workbench per extracted project, on an available loopback port."""
import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import msvcrt
from pathlib import Path
import secrets
import sys
import time
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from debug_ui.server import Jobs, make_handler


def show(url, open_browser):
    print(f'CLinkRAG  {url}', flush=True)
    if open_browser:
        webbrowser.open(url)


def reopen(state_path, open_browser):
    # The lock owner may still be starting. Check the running service's identity
    # before opening a port remembered from an older session.
    client = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for _ in range(25):
        try:
            state = json.loads(state_path.read_text('utf-8'))
            url = f'http://127.0.0.1:{int(state["port"])}/'
            with client.open(url + 'api/config', timeout=0.4) as response:
                token = json.load(response)['token']
            if secrets.compare_digest(hashlib.sha256(token.encode()).hexdigest(), state['identity']):
                show(url, open_browser)
                return
        except (OSError, ValueError, KeyError):
            pass
        time.sleep(0.12)
    raise RuntimeError('同目录中的服务仍在启动或关闭。请稍后重新打开。')


def bind(preferred, allow_fallback):
    try:
        return ThreadingHTTPServer(('127.0.0.1', preferred), BaseHTTPRequestHandler)
    except OSError as exc:
        # Windows also reports WSAEACCES for a port bound exclusively by another app.
        if not allow_fallback or not preferred or exc.winerror not in (10013, 10048):
            raise
        return ThreadingHTTPServer(('127.0.0.1', 0), BaseHTTPRequestHandler)


def serve(port, open_browser, allow_fallback):
    state_dir = ROOT / '.cache' / 'launcher'
    state_dir.mkdir(parents=True, exist_ok=True)
    state_path = state_dir / 'instance.json'
    with (state_dir / 'instance.lock').open('a+b') as lock:
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            reopen(state_path, open_browser)
            return
        with bind(port, allow_fallback) as server:
            jobs = Jobs()
            try:
                token = secrets.token_urlsafe(32)
                server.RequestHandlerClass = make_handler(jobs, token)
                state = {'port': server.server_port, 'identity': hashlib.sha256(token.encode()).hexdigest()}
                temp = state_path.with_suffix('.tmp')
                temp.write_text(json.dumps(state), encoding='utf-8')
                temp.replace(state_path)
                show(f'http://127.0.0.1:{server.server_port}/', open_browser)
                print('保留此窗口以继续使用。按 Ctrl+C 可停止服务。', flush=True)
                server.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                state_path.unlink(missing_ok=True)
                jobs.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    serve(args.port, open_browser=not args.no_browser, allow_fallback=True)
