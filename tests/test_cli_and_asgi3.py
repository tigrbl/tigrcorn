import unittest

from tigrcorn.cli import build_parser
from tigrcorn.compat.asgi3 import assert_asgi3_app, describe_app, is_http_event, is_http_scope, is_lifespan_scope, is_websocket_scope


class CLIAndASGI3Tests(unittest.TestCase):
    def test_parser(self):
        parser = build_parser()
        ns = parser.parse_args([
            'tests.fixtures_pkg.appmod:app',
            '--transport', 'udp',
            '--protocol', 'http3',
            '--http', '3',
            '--ssl-ca-certs', 'ca.pem',
            '--ssl-require-client-cert',
        ])
        self.assertEqual(ns.transport, 'udp')
        self.assertEqual(ns.protocols, ['http3'])
        self.assertEqual(ns.http_versions, ['3'])
        self.assertEqual(ns.ssl_ca_certs, 'ca.pem')
        self.assertTrue(ns.ssl_require_client_cert)

    def test_asgi3_helpers(self):
        async def app(scope, receive, send):
            return None
        info = describe_app(app)
        self.assertEqual(info.parameter_count, 3)
        assert_asgi3_app(app)
        self.assertTrue(is_http_scope({'type': 'http'}))
        self.assertTrue(is_websocket_scope({'type': 'websocket'}))
        self.assertTrue(is_lifespan_scope({'type': 'lifespan'}))
        self.assertTrue(is_http_event({'type': 'http.request'}))
