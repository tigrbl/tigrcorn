import unittest

from tigrcorn.config.load import build_config
from tigrcorn.config.model import ListenerConfig, ServerConfig
from tigrcorn.config.validate import validate_config
from tigrcorn.errors import ConfigError


class ConfigMatrixTests(unittest.TestCase):
    def test_tcp_defaults(self):
        config = build_config(host='127.0.0.1', port=1234, lifespan='off')
        listener = config.listeners[0]
        self.assertEqual(listener.kind, 'tcp')
        self.assertIn('http1', listener.enabled_protocols)
        self.assertIn('websocket', listener.enabled_protocols)

    def test_udp_http3_defaults(self):
        config = build_config(
            transport='udp',
            host='127.0.0.1',
            port=9443,
            lifespan='off',
            http_versions=['3'],
            protocols=['http3'],
        )
        listener = config.listeners[0]
        self.assertEqual(listener.kind, 'udp')
        self.assertEqual(listener.scheme, 'https')
        self.assertEqual(listener.enabled_protocols[:2], ('quic', 'http3'))

    def test_pipe_label(self):
        listener = ListenerConfig(kind='pipe', path='/tmp/tigrcorn.pipe')
        self.assertEqual(listener.label, 'pipe:///tmp/tigrcorn.pipe')
        self.assertEqual(listener.enabled_protocols, ('rawframed',))

    def test_udp_ssl_is_accepted_for_quic_tls(self):
        config = ServerConfig(listeners=[ListenerConfig(kind='udp', host='127.0.0.1', port=1, ssl_certfile='x', ssl_keyfile='y')])
        validate_config(config)

    def test_udp_client_auth_is_accepted_with_a_trust_store(self):
        config = ServerConfig(
            listeners=[
                ListenerConfig(
                    kind='udp',
                    host='127.0.0.1',
                    port=1,
                    ssl_certfile='x',
                    ssl_keyfile='y',
                    ssl_ca_certs='ca.pem',
                    ssl_require_client_cert=True,
                )
            ]
        )
        validate_config(config)

    def test_udp_client_auth_requires_an_explicit_trust_store(self):
        config = ServerConfig(
            listeners=[
                ListenerConfig(
                    kind='udp',
                    host='127.0.0.1',
                    port=1,
                    ssl_certfile='x',
                    ssl_keyfile='y',
                    ssl_require_client_cert=True,
                )
            ]
        )
        with self.assertRaises(ConfigError):
            validate_config(config)


    def test_tcp_client_auth_is_accepted_with_a_trust_store(self):
        config = ServerConfig(
            listeners=[
                ListenerConfig(
                    kind='tcp',
                    host='127.0.0.1',
                    port=1,
                    ssl_certfile='x',
                    ssl_keyfile='y',
                    ssl_ca_certs='ca.pem',
                    ssl_require_client_cert=True,
                )
            ]
        )
        validate_config(config)

    def test_tcp_client_auth_requires_an_explicit_trust_store(self):
        config = ServerConfig(
            listeners=[
                ListenerConfig(
                    kind='tcp',
                    host='127.0.0.1',
                    port=1,
                    ssl_certfile='x',
                    ssl_keyfile='y',
                    ssl_require_client_cert=True,
                )
            ]
        )
        with self.assertRaises(ConfigError):
            validate_config(config)

    def test_invalid_pipe_requires_path(self):
        config = ServerConfig(listeners=[ListenerConfig(kind='pipe', path=None)])
        with self.assertRaises(ConfigError):
            validate_config(config)
