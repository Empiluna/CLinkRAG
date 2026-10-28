"""Read a configured provider's model directory without sending inference requests."""
from datetime import datetime, timezone
import hashlib
import threading
import time
from urllib.parse import urlsplit

import requests

from llms.settings import configured_key, provider
from debug_ui.model_settings import public_values


class ModelCatalog:
    def __init__(self, loader):
        self.loader = loader
        self.lock = threading.Lock()
        self.cache = {}

    def list(self, refresh=False, config=None):
        config = self.loader() if config is None else config
        values = public_values(config)
        kind = provider(config)
        key = configured_key(config)
        url_key = {'deepseek': 'DEEPSEEK_BASE_URL', 'anthropic': 'ANTHROPIC_BASE_URL',
                   'qwen': 'QWEN_BASE_URL'}.get(kind, 'OPENAI_BASE_URL')
        base = values[url_key].rstrip('/')
        current = values['MODEL_NAME']
        fallback = [{'id': current, 'name': current}] if current and key else []
        if not key:
            return {'models': [], 'source': 'fallback', 'message': '请先在设置中配置模型服务。'}
        parsed = urlsplit(base)
        if (not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment
                or (parsed.scheme != 'https' and not (parsed.scheme == 'http' and
                    parsed.hostname in ('localhost', '127.0.0.1', '::1')))):
            return {'models': fallback, 'source': 'fallback', 'message': '模型服务地址格式不正确。'}
        fingerprint = hashlib.sha256(f'{kind}\0{base}\0{key}'.encode()).hexdigest()
        with self.lock:
            cached = self.cache.get(fingerprint)
            ttl = 300 if cached and cached[1]['source'] == 'api' else 30
            if not refresh and cached and time.monotonic() - cached[0] < ttl:
                result = {**cached[1], 'cached': True}
            else:
                result = self._fetch(base, kind, key)
                # Keep only the current credential/endpoint directory in memory.
                self.cache = {fingerprint: (time.monotonic(), result)}
        if result['source'] != 'api':
            result = {**result, 'models': fallback}
        return result

    def _fetch(self, base, kind, key):
        url = base + ('/models' if kind != 'anthropic' or base.endswith('/v1') else '/v1/models')
        headers = {'Accept': 'application/json'}
        if kind == 'anthropic':
            headers.update({'x-api-key': key, 'anthropic-version': '2023-06-01'})
        else:
            headers['Authorization'] = 'Bearer ' + key
        params = {'limit': 100} if kind == 'anthropic' else {}
        models, seen, cursor = [], set(), None
        try:
            with requests.Session() as session:
                for page in range(10):
                    with session.get(url, headers=headers, params=params, timeout=(5, 15),
                                     allow_redirects=False, stream=True) as response:
                        if response.status_code != 200:
                            messages = {401: '模型列表鉴权失败，请检查 API 密钥。',
                                        403: '当前 API 无权读取模型列表。',
                                        404: '当前服务未提供模型列表接口。',
                                        405: '当前服务未提供模型列表接口。',
                                        429: '模型列表请求过于频繁，请稍后刷新。'}
                            raise ValueError(messages.get(response.status_code, '模型服务暂时未返回列表。'))
                        body = bytearray()
                        for part in response.iter_content(65536):
                            body.extend(part)
                            if len(body) > 2_000_000:
                                raise ValueError('模型列表过大，请在设置中指定模型。')
                        import json
                        try:
                            payload = json.loads(body)
                        except (ValueError, UnicodeError):
                            raise ValueError('模型服务返回了无法识别的列表。') from None
                    rows = payload.get('data') if isinstance(payload, dict) else None
                    if not isinstance(rows, list):
                        raise ValueError('模型服务返回了无法识别的列表。')
                    for row in rows:
                        if not isinstance(row, dict):
                            continue
                        identity = row.get('id')
                        if (not isinstance(identity, str) or not identity.strip() or len(identity) > 512
                                or any(ord(c) < 32 for c in identity) or identity in seen):
                            continue
                        output = row.get('output_modalities')
                        if isinstance(output, list) and output and 'text' not in output:
                            continue
                        seen.add(identity)
                        name = row.get('display_name') or row.get('name') or identity
                        models.append({'id': identity, 'name': name[:200] if isinstance(name, str) else identity})
                    if not payload.get('has_more'):
                        break
                    next_cursor = payload.get('last_id') or (rows[-1].get('id') if rows and isinstance(rows[-1], dict) else None)
                    if not isinstance(next_cursor, str) or next_cursor == cursor or page == 9:
                        raise ValueError('模型列表分页未能完整读取，请稍后刷新。')
                    cursor = next_cursor
                    params['after_id'] = cursor
            return {'models': models, 'source': 'api', 'message': '', 'cached': False,
                    'fetched_at': datetime.now(timezone.utc).isoformat()}
        except requests.RequestException:
            message = '连接模型列表接口失败，请稍后刷新。'
        except ValueError as error:
            message = str(error)
        return {'models': [], 'source': 'fallback', 'message': message, 'cached': False}
