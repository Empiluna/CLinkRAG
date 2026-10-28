"""Public proxy mode must reject unauthenticated and cross-site requests."""
import base64
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from debug_ui.server import Jobs, make_handler


class PublicProxyTests(unittest.TestCase):
    def test_password_and_origin_are_required(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch('debug_ui.server.PUBLIC_ORIGIN', 'https://clinkrag.hifuu.space'), \
                patch('debug_ui.server.AUTH_USER', 'research'), \
                patch('debug_ui.server.AUTH_PASSWORD', 'test-only-password'):
            server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(Jobs(Path(directory)), 'fixture-token'))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            auth = 'Basic ' + base64.b64encode(b'research:test-only-password').decode()

            def request(method, path, headers=None, body=None):
                connection = HTTPConnection('127.0.0.1', server.server_port, timeout=3)
                try:
                    connection.request(method, path, body=body, headers=headers or {})
                    response = connection.getresponse()
                    return response.status, dict(response.getheaders()), response.read()
                finally:
                    connection.close()

            try:
                status, headers, _ = request('GET', '/api/config')
                self.assertEqual(status, 401)
                self.assertIn('Basic', headers['WWW-Authenticate'])
                self.assertEqual(request('GET', '/api/config', {'Authorization': auth})[0], 200)
                payload = b'{}'
                common = {'Authorization': auth, 'X-SciRAG-Token': 'fixture-token'}
                self.assertEqual(request('POST', '/api/runs', {**common, 'Origin': 'https://other.invalid'}, payload)[0], 403)
                self.assertEqual(request('POST', '/api/runs', {**common, 'Origin': 'https://clinkrag.hifuu.space'}, payload)[0], 400)
            finally:
                server.shutdown()
                server.server_close()
                thread.join()


if __name__ == '__main__':
    unittest.main()
