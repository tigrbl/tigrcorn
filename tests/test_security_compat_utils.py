import unittest

from tigrcorn.compat.conformance import compare_sequence, normalize_scope
from tigrcorn.compat.hypercorn import HYPERCORN_COMPAT
from tigrcorn.compat.uvicorn import UVICORN_COMPAT
from tigrcorn.security.alpn import normalize_alpn
from tigrcorn.security.certs import PeerCertificate
from tigrcorn.security.policies import TLSPolicy
from tigrcorn.security.tls import build_server_ssl_context
from tigrcorn.config.model import ListenerConfig
from tigrcorn.utils.ids import next_id, next_session_id, next_stream_id


class SecurityCompatUtilsTests(unittest.TestCase):
    def test_alpn_and_policy(self):
        self.assertEqual(normalize_alpn('h2'), 'h2')
        self.assertIsNone(normalize_alpn(''))
        cert = PeerCertificate(serial_number='abc')
        self.assertEqual(cert.serial_number, 'abc')
        policy = TLSPolicy(require_client_cert=True)
        self.assertTrue(policy.require_client_cert)
        self.assertIsNone(build_server_ssl_context(ListenerConfig()))

    def test_compat_profiles_and_conformance(self):
        self.assertTrue(UVICORN_COMPAT.http1)
        self.assertTrue(HYPERCORN_COMPAT.http2)
        left = [{'type': 'http.response.start', 'headers': [(b'a', b'b')]}]
        right = [{'type': 'http.response.start', 'headers': [(b'a', b'b')]}]
        diff = compare_sequence(left, right)
        self.assertTrue(diff.ok)
        self.assertNotIn('state', normalize_scope({'type': 'http', 'state': {}}))

    def test_ids_monotonic(self):
        a, b = next_id(), next_id()
        self.assertLess(a, b)
        self.assertLess(next_session_id(), next_session_id())
        self.assertLess(next_stream_id(), next_stream_id())
