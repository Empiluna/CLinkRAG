import sys,unittest
from pathlib import Path
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'longans'))
import s2_transport as t

class TransportTests(unittest.TestCase):
    def test_rate_limit_retries_and_preserves_headers(self):
        limited=Mock(status_code=429,headers={'Retry-After':'5'})
        good=Mock(status_code=200)
        with patch.object(t.time,'sleep') as sleep, patch.object(t.requests,'get',side_effect=[limited,good]) as get:
            result=t.request('GET','https://api.semanticscholar.org/graph/v1/paper/example',headers={'x-api-key':'test-only'})
        self.assertIs(result,good)
        self.assertEqual(get.call_count,2)
        self.assertEqual(get.call_args.kwargs['headers'],{'x-api-key':'test-only'})
        self.assertTrue(any(c.args==(5.0,) for c in sleep.call_args_list))
        limited.close.assert_called_once()

    def test_retry_limit_is_bounded(self):
        response=Mock(status_code=429,headers={})
        with patch.object(t.time,'sleep'),patch.object(t.requests,'get',return_value=response) as get:
            self.assertIs(t.request('GET','https://api.semanticscholar.org/graph/v1/paper/example'),response)
        self.assertEqual(get.call_count,t.MAX_ATTEMPTS)

    def test_auth_error_is_not_retried(self):
        response=Mock(status_code=403)
        with patch.object(t.time,'sleep'),patch.object(t.requests,'get',return_value=response) as get:
            self.assertIs(t.request('GET','https://api.semanticscholar.org/graph/v1/paper/example'),response)
        get.assert_called_once()

    def test_other_host_rejected(self):
        with self.assertRaises(ValueError):
            t.request('GET','https://api.semanticscholar.org.example.com/')
