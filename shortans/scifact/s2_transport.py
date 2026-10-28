"""Paced Semantic Scholar requests with bounded HTTP and connection retries."""
import threading
import time
import requests
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
from urllib.parse import urlsplit

_lock = threading.Lock()
_last_finished = 0.0
MIN_INTERVAL = 1.2
MAX_ATTEMPTS = 4


class SemanticScholarConnectionError(requests.exceptions.ConnectionError):
    """Readable failure with the underlying exception retained as its cause."""


def _transient_connection(error):
    if isinstance(error, requests.exceptions.SSLError):
        # Never retry certificate verification failures or disable verification.
        message = str(error).lower()
        if any(term in message for term in ('certificate', 'hostname mismatch')):
            return False
        return any(term in message for term in (
            'unexpected_eof', 'eof occurred', 'connection reset', 'connection aborted'))
    return isinstance(error, (requests.exceptions.ConnectionError,
                              requests.exceptions.Timeout,
                              requests.exceptions.ChunkedEncodingError))


def _pause(delay, attempt, reason, on_retry):
    event = {'failed_attempt': attempt + 1, 'next_attempt': attempt + 2,
             'max_attempts': MAX_ATTEMPTS, 'delay_seconds': delay, 'reason': reason}
    print(f'Semantic Scholar: {reason}; retry {attempt + 2}/{MAX_ATTEMPTS} in {delay:.0f}s.', flush=True)
    if on_retry is not None:
        on_retry(event)
    time.sleep(delay)


def _retry_delay(response, attempt):
    value = response.headers.get('Retry-After', '')
    try:
        seconds = float(value)
    except (ValueError, TypeError):
        try:
            seconds = (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds()
        except (ValueError, TypeError, OverflowError):
            seconds = 0
    return max(4 * (2 ** attempt), min(60, max(0, seconds)))


def request(method, url, *, on_retry=None, **kwargs):
    global _last_finished
    if not url.startswith('https://api.semanticscholar.org/'):
        raise ValueError('Semantic Scholar transport only accepts the official API host.')
    kwargs.setdefault('timeout', (15, 60))
    # The POST batch endpoint only reads papers; other mutations are not replayed.
    replayable = method.upper() in ('GET', 'HEAD') or (
        method.upper() == 'POST' and urlsplit(url).path == '/graph/v1/paper/batch')
    # A single lock coordinates every query thread, including cooldown after 429.
    with _lock:
        for attempt in range(MAX_ATTEMPTS):
            time.sleep(max(0, MIN_INTERVAL - (time.monotonic() - _last_finished)))
            try:
                response = getattr(requests, method.lower())(url, **kwargs)
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout,
                    requests.exceptions.ChunkedEncodingError) as exc:
                _last_finished = time.monotonic()
                transient = _transient_connection(exc)
                if not transient:
                    raise SemanticScholarConnectionError(
                        '无法建立与 Semantic Scholar 的安全连接。请检查代理和系统证书配置；'
                        '本次未重试此 TLS 错误，技术记录保留了原始原因。') from exc
                if not replayable or attempt == MAX_ATTEMPTS - 1:
                    raise SemanticScholarConnectionError(
                        f'Semantic Scholar 检索连接中断或超时，已尝试 {attempt + 1} 次仍未恢复。'
                        '请检查网络或代理连接后重新研究；已获取的资料保留在本次记录中。') from exc
                reason = ('安全连接意外断开' if isinstance(exc, requests.exceptions.SSLError)
                          else '请求超时' if isinstance(exc, requests.exceptions.Timeout)
                          else '网络连接中断')
                _pause(2 * (2 ** attempt), attempt, reason, on_retry)
                continue
            _last_finished = time.monotonic()
            if (not replayable or response.status_code not in (429, 502, 503, 504)
                    or attempt == MAX_ATTEMPTS - 1):
                return response
            delay = _retry_delay(response, attempt)
            response.close()
            _pause(delay, attempt, f'HTTP {response.status_code}', on_retry)
    raise RuntimeError('Unreachable transport state')
