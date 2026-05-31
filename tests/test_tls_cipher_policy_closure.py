from __future__ import annotations

import asyncio
import contextlib
import json
import os
import socket
import ssl
import tempfile
import unittest
from pathlib import Path

from tigrcorn.compat.release_gates import evaluate_promotion_target
from tigrcorn.config.load import build_config
from tigrcorn.constants import DEFAULT_QUIC_SECRET
from tigrcorn.errors import ConfigError
from tigrcorn.security.tls import build_server_ssl_context
from tigrcorn.security.tls13.handshake import generate_self_signed_certificate
from tigrcorn.server.runner import TigrCornServer
from tigrcorn.transports.quic.connection import QuicConnection
from tigrcorn.transports.quic.handshake import QuicTlsHandshakeDriver

ROOT = Path(__file__).resolve().parents[1]
CONFORMANCE = ROOT / 'docs' / 'review' / 'conformance'


async def _start_tls_server(*, ssl_ciphers: str):
    async def app(scope, receive, send):
        await receive()
        await send({'type': 'http.response.start', 'status': 204, 'headers': []})
        await send({'type': 'http.response.body', 'body': b'', 'more_body': False})

    cert_pem, key_pem = generate_self_signed_certificate('server.example')
    tmpdir = tempfile.TemporaryDirectory()
    certfile = os.path.join(tmpdir.name, 'server-cert.pem')
    keyfile = os.path.join(tmpdir.name, 'server-key.pem')
    Path(certfile).write_bytes(cert_pem)
    Path(keyfile).write_bytes(key_pem)
    config = build_config(
        host='127.0.0.1',
        port=0,
        lifespan='off',
        http_versions=['1.1'],
        ssl_certfile=certfile,
        ssl_keyfile=keyfile,
        ssl_ciphers=ssl_ciphers,
    )
    server = TigrCornServer(app, config)
    await server.start()
    port = server._listeners[0].server.sockets[0].getsockname()[1]
    return tmpdir, cert_pem, server, port


async def _start_http3_server(*, ssl_ciphers: str):
    async def app(scope, receive, send):
        await send({'type': 'http.response.start', 'status': 204, 'headers': []})
        await send({'type': 'http.response.body', 'body': b'', 'more_body': False})

    cert_pem, key_pem = generate_self_signed_certificate('server.example')
    tmpdir = tempfile.TemporaryDirectory()
    certfile = os.path.join(tmpdir.name, 'server-cert.pem')
    keyfile = os.path.join(tmpdir.name, 'server-key.pem')
    Path(certfile).write_bytes(cert_pem)
    Path(keyfile).write_bytes(key_pem)
    config = build_config(
        transport='udp',
        host='127.0.0.1',
        port=0,
        lifespan='off',
        http_versions=['3'],
        protocols=['http3'],
        ssl_certfile=certfile,
        ssl_keyfile=keyfile,
        ssl_ciphers=ssl_ciphers,
    )
    server = TigrCornServer(app, config)
    await server.start()
    port = server._listeners[0].transport.get_extra_info('sockname')[1]
    return tmpdir, cert_pem, server, port


class Phase9F1TLSCipherPolicyTests(unittest.IsolatedAsyncioTestCase):
    def test_cli_and_config_runtime_fields_resolve_ssl_ciphers(self):
        config = build_config(
            host='127.0.0.1',
            port=0,
            ssl_certfile='tests/fixtures_certs/interop-localhost-cert.pem',
            ssl_keyfile='tests/fixtures_certs/interop-localhost-key.pem',
            ssl_ciphers='TLS_AES_128_GCM_SHA256',
        )
        self.assertEqual(config.tls.resolved_cipher_suites, (0x1301,))
        self.assertEqual(config.listeners[0].ssl_ciphers, 'TLS_AES_128_GCM_SHA256')
        self.assertEqual(config.listeners[0].resolved_cipher_suites, (0x1301,))

    def test_invalid_ssl_cipher_expressions_fail_fast(self):
        with self.assertRaises(ConfigError):
            build_config(
                host='127.0.0.1',
                port=0,
                ssl_certfile='tests/fixtures_certs/interop-localhost-cert.pem',
                ssl_keyfile='tests/fixtures_certs/interop-localhost-key.pem',
                ssl_ciphers='TLS_FAKE_CIPHER',
            )

    def test_build_server_ssl_context_carries_resolved_cipher_suites(self):
        config = build_config(
            host='127.0.0.1',
            port=0,
            ssl_certfile='tests/fixtures_certs/interop-localhost-cert.pem',
            ssl_keyfile='tests/fixtures_certs/interop-localhost-key.pem',
            ssl_ciphers='TLS_AES_128_GCM_SHA256',
        )
        context = build_server_ssl_context(config.listeners[0])
        self.assertIsNotNone(context)
        assert context is not None
        self.assertEqual(context.cipher_suites, (0x1301,))

    async def test_tcp_tls_negotiated_suite_changes_with_configured_allowlist(self):
        tmpdir, cert_pem, server, port = await _start_tls_server(ssl_ciphers='TLS_AES_128_GCM_SHA256')
        try:
            ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=None)
            cafile = Path(tmpdir.name) / 'trusted.pem'
            cafile.write_bytes(cert_pem)
            ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=str(cafile))
            ctx.minimum_version = ssl.TLSVersion.TLSv1_3
            ctx.set_alpn_protocols(['http/1.1'])
            reader, writer = await asyncio.open_connection('127.0.0.1', port, ssl=ctx, server_hostname='server.example')
            try:
                self.assertEqual(writer.get_extra_info('ssl_object').cipher()[0], 'TLS_AES_128_GCM_SHA256')
                writer.write(b'POST / HTTP/1.1\r\nHost: server.example\r\nContent-Length: 0\r\n\r\n')
                await writer.drain()
                data = await reader.read(65535)
                self.assertIn(b'204 No Content', data)
            finally:
                writer.close()
                with contextlib.suppress(Exception):
                    await writer.wait_closed()
        finally:
            await server.close()
            tmpdir.cleanup()

    async def test_quic_tls_negotiated_suite_changes_with_configured_allowlist(self):
        tmpdir, cert_pem, server, port = await _start_http3_server(ssl_ciphers='TLS_AES_128_GCM_SHA256')
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setblocking(False)
            client = QuicConnection(is_client=True, secret=DEFAULT_QUIC_SECRET, local_cid=b'cli1cli1')
            client.configure_handshake(
                QuicTlsHandshakeDriver(
                    is_client=True,
                    server_name='server.example',
                    trusted_certificates=[cert_pem],
                )
            )
            loop = asyncio.get_running_loop()
            sock.sendto(client.start_handshake(), ('127.0.0.1', port))
            for _ in range(12):
                data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 1.0)
                for _event in client.receive_datagram(data):
                    pass
                for datagram in client.take_handshake_datagrams():
                    sock.sendto(datagram, ('127.0.0.1', port))
                if client.handshake_driver is not None and client.handshake_driver.complete:
                    break
            self.assertIsNotNone(client.handshake_driver)
            assert client.handshake_driver is not None
            self.assertTrue(client.handshake_driver.complete)
            self.assertEqual(client.handshake_driver._selected_cipher_suite, 0x1301)
            sock.close()
        finally:
            await server.close()
            tmpdir.cleanup()

    def test_phase9f1_status_snapshot_matches_current_flag_surface_state(self):
        payload = json.loads((CONFORMANCE / 'phase9f1_tls_cipher_policy.current.json').read_text(encoding='utf-8'))
        self.assertEqual(payload['phase'], '9F1')
        self.assertEqual(payload['implemented_flag'], '--ssl-ciphers')
        self.assertNotIn('--ssl-ciphers', payload['current_state']['remaining_flag_runtime_blockers'])
        failures = '\n'.join(evaluate_promotion_target(ROOT).flag_surface.failures)
        self.assertNotIn('--ssl-ciphers', failures)


if __name__ == '__main__':
    unittest.main()
