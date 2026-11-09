from __future__ import annotations

import asyncio
import base64
import tempfile
import unittest
import zlib
from pathlib import Path

from tigrcorn.cli import build_parser
from tigrcorn.config.load import build_config, build_config_from_namespace
from tigrcorn.protocols.websocket.frames import encode_frame, read_frame
from tigrcorn.security.tls import build_server_ssl_context
from tigrcorn.server.runner import TigrCornServer
from tigrcorn.security.tls13.handshake import generate_self_signed_certificate


async def _start_http11_server(app, *, config_mutator=None):
    config = build_config(app=None, host='127.0.0.1', port=0, lifespan='off', http_versions=['1.1'])
    if config_mutator is not None:
        config_mutator(config)
    server = TigrCornServer(app, config)
    await server.start()
    port = server._listeners[0].server.sockets[0].getsockname()[1]
    return server, port


def _compress_ws_message(payload: bytes) -> bytes:
    compressor = zlib.compressobj(wbits=-15)
    compressed = compressor.compress(payload) + compressor.flush(zlib.Z_SYNC_FLUSH)
    assert compressed.endswith(b'\x00\x00\xff\xff')
    return compressed[:-4]


class Phase3StrictRFCSurfaceTests(unittest.IsolatedAsyncioTestCase):
    async def test_cli_phase3_flags_round_trip_into_config(self):
        parser = build_parser()
        ns = parser.parse_args([
            'tests.fixtures_pkg.appmod:app',
            '--ssl-ocsp-mode', 'require',
            '--ssl-ocsp-soft-fail',
            '--ssl-ocsp-cache-size', '64',
            '--ssl-ocsp-max-age', '30',
            '--ssl-crl-mode', 'soft-fail',
            '--ssl-revocation-fetch', 'off',
            '--ssl-alpn', 'h2,http/1.1',
            '--connect-policy', 'allowlist',
            '--connect-allow', '127.0.0.1:443,10.0.0.0/8',
            '--trailer-policy', 'drop',
            '--content-coding-policy', 'strict',
            '--content-codings', 'gzip,deflate',
            '--websocket-compression', 'permessage-deflate',
        ])
        config = build_config_from_namespace(ns)
        self.assertEqual(config.tls.ocsp_mode, 'require')
        self.assertTrue(config.tls.ocsp_soft_fail)
        self.assertEqual(config.tls.ocsp_cache_size, 64)
        self.assertEqual(config.tls.ocsp_max_age, 30)
        self.assertEqual(config.tls.crl_mode, 'soft-fail')
        self.assertFalse(config.tls.revocation_fetch)
        self.assertEqual(config.tls.alpn_protocols, ['h2', 'http/1.1'])
        self.assertEqual(config.http.connect_policy, 'allowlist')
        self.assertEqual(config.http.connect_allow, ['127.0.0.1:443', '10.0.0.0/8'])
        self.assertEqual(config.http.trailer_policy, 'drop')
        self.assertEqual(config.http.content_coding_policy, 'strict')
        self.assertEqual(config.http.content_codings, ['gzip', 'deflate'])
        self.assertEqual(config.websocket.compression, 'permessage-deflate')

    async def test_http11_websocket_compression_auto_negotiates_when_enabled(self):
        seen = {}

        async def app(scope, receive, send):
            await receive()
            await send({'type': 'websocket.accept'})
            event = await receive()
            seen['event'] = event
            await send({'type': 'websocket.send', 'text': event['text']})
            await send({'type': 'websocket.close', 'code': 1000})

        def _mutate(config):
            config.websocket.enabled = True
            config.listeners[0].websocket = True
            config.websocket.compression = 'permessage-deflate'

        server, port = await _start_http11_server(app, config_mutator=_mutate)
        try:
            reader, writer = await asyncio.open_connection('127.0.0.1', port)
            key = base64.b64encode(b'0123456789abcdef')
            writer.write(
                b'GET /ws HTTP/1.1\r\n'
                b'Host: localhost\r\n'
                b'Upgrade: websocket\r\n'
                b'Connection: Upgrade\r\n'
                b'Sec-WebSocket-Version: 13\r\n'
                b'Sec-WebSocket-Key: ' + key + b'\r\n'
                b'Sec-WebSocket-Extensions: permessage-deflate\r\n\r\n'
            )
            await writer.drain()
            response = await reader.readuntil(b'\r\n\r\n')
            self.assertIn(b'sec-websocket-extensions: permessage-deflate', response.lower())
            writer.write(encode_frame(0x1, _compress_ws_message(b'hello compressed'), masked=True, rsv1=True))
            await writer.drain()
            frame = await asyncio.wait_for(read_frame(reader, max_payload_size=4096, expect_masked=False, allow_rsv1=True), 1.0)
            self.assertTrue(frame.rsv1)
            echoed = zlib.decompressobj(wbits=-15).decompress(frame.payload + b'\x00\x00\xff\xff')
            self.assertEqual(echoed, b'hello compressed')
            self.assertEqual(seen['event']['text'], 'hello compressed')
            writer.close()
            await writer.wait_closed()
        finally:
            await server.close()

    async def test_http11_websocket_compression_policy_off_strips_app_requested_extension(self):
        async def app(scope, receive, send):
            await receive()
            await send({'type': 'websocket.accept', 'headers': [(b'sec-websocket-extensions', b'permessage-deflate')]})
            await send({'type': 'websocket.close', 'code': 1000})

        def _mutate(config):
            config.websocket.enabled = True
            config.listeners[0].websocket = True
            config.websocket.compression = 'off'

        server, port = await _start_http11_server(app, config_mutator=_mutate)
        try:
            reader, writer = await asyncio.open_connection('127.0.0.1', port)
            key = base64.b64encode(b'fedcba9876543210')
            writer.write(
                b'GET /ws HTTP/1.1\r\n'
                b'Host: localhost\r\n'
                b'Upgrade: websocket\r\n'
                b'Connection: Upgrade\r\n'
                b'Sec-WebSocket-Version: 13\r\n'
                b'Sec-WebSocket-Key: ' + key + b'\r\n'
                b'Sec-WebSocket-Extensions: permessage-deflate\r\n\r\n'
            )
            await writer.drain()
            response = await reader.readuntil(b'\r\n\r\n')
            self.assertNotIn(b'sec-websocket-extensions:', response.lower())
            writer.close()
            await writer.wait_closed()
        finally:
            await server.close()

    async def test_http11_connect_policy_deny_and_allowlist(self):
        received = bytearray()

        async def upstream_handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
            data = await reader.read(1024)
            received.extend(data)
            writer.write(data[::-1])
            await writer.drain()
            writer.close()
            await writer.wait_closed()

        upstream = await asyncio.start_server(upstream_handler, '127.0.0.1', 0)
        upstream_port = upstream.sockets[0].getsockname()[1]
        try:
            async def app(scope, receive, send):
                raise AssertionError('CONNECT should not dispatch to ASGI app')

            def deny(config):
                config.http.connect_policy = 'deny'

            server, port = await _start_http11_server(app, config_mutator=deny)
            try:
                reader, writer = await asyncio.open_connection('127.0.0.1', port)
                writer.write(f'CONNECT 127.0.0.1:{upstream_port} HTTP/1.1\r\nHost: localhost\r\n\r\n'.encode('ascii'))
                await writer.drain()
                head = await reader.readuntil(b'\r\n\r\n')
                self.assertIn(b'403', head)
                writer.close()
                await writer.wait_closed()
            finally:
                await server.close()

            def allowlist(config):
                config.http.connect_policy = 'allowlist'
                config.http.connect_allow = [f'127.0.0.1:{upstream_port}']

            server, port = await _start_http11_server(app, config_mutator=allowlist)
            try:
                reader, writer = await asyncio.open_connection('127.0.0.1', port)
                writer.write(f'CONNECT 127.0.0.1:{upstream_port} HTTP/1.1\r\nHost: localhost\r\n\r\n'.encode('ascii'))
                await writer.drain()
                head = await reader.readuntil(b'\r\n\r\n')
                self.assertIn(b'200 Connection Established', head)
                writer.write(b'abcdef')
                await writer.drain()
                echoed = await asyncio.wait_for(reader.readexactly(6), 1.0)
                self.assertEqual(echoed, b'fedcba')
                self.assertEqual(bytes(received), b'abcdef')
                writer.close()
                await writer.wait_closed()
            finally:
                await server.close()
        finally:
            upstream.close()
            await upstream.wait_closed()

    async def test_http11_trailer_policy_drop_suppresses_trailer_event(self):
        seen_types = []

        async def app(scope, receive, send):
            while True:
                message = await receive()
                seen_types.append(message['type'])
                if message['type'] == 'http.request' and not message.get('more_body', False):
                    break
                if message['type'] == 'http.disconnect':
                    break
            await send({'type': 'http.response.start', 'status': 204, 'headers': []})
            await send({'type': 'http.response.body', 'body': b'', 'more_body': False})

        def _mutate(config):
            config.http.trailer_policy = 'drop'

        server, port = await _start_http11_server(app, config_mutator=_mutate)
        try:
            reader, writer = await asyncio.open_connection('127.0.0.1', port)
            writer.write(
                b'POST / HTTP/1.1\r\n'
                b'Host: localhost\r\n'
                b'Transfer-Encoding: chunked\r\n\r\n'
                b'5\r\nhello\r\n'
                b'0\r\nX-Test: yes\r\n\r\n'
            )
            await writer.drain()
            await reader.readuntil(b'\r\n\r\n')
            self.assertNotIn('http.request.trailers', seen_types)
            writer.close()
            await writer.wait_closed()
        finally:
            await server.close()

    async def test_http11_content_coding_identity_only_disables_gzip(self):
        async def app(scope, receive, send):
            await receive()
            await send({'type': 'http.response.start', 'status': 200, 'headers': [(b'content-type', b'text/plain')]})
            await send({'type': 'http.response.body', 'body': b'compress-me', 'more_body': False})

        def _mutate(config):
            config.http.content_coding_policy = 'identity-only'
            config.http.content_codings = ['gzip', 'deflate']

        server, port = await _start_http11_server(app, config_mutator=_mutate)
        try:
            reader, writer = await asyncio.open_connection('127.0.0.1', port)
            writer.write(
                b'GET / HTTP/1.1\r\n'
                b'Host: localhost\r\n'
                b'Accept-Encoding: gzip\r\n\r\n'
            )
            await writer.drain()
            head = await reader.readuntil(b'\r\n\r\n')
            self.assertNotIn(b'content-encoding: gzip', head.lower())
            writer.close()
            await writer.wait_closed()
        finally:
            await server.close()

    def test_build_server_ssl_context_uses_public_alpn_and_revocation_policy(self):
        try:
            cert_pem, key_pem = generate_self_signed_certificate('server.example')
        except ModuleNotFoundError as exc:
            self.skipTest(str(exc))
        with tempfile.TemporaryDirectory() as tmp:
            cert_path = Path(tmp) / 'cert.pem'
            key_path = Path(tmp) / 'key.pem'
            ca_path = Path(tmp) / 'ca.pem'
            cert_path.write_bytes(cert_pem)
            key_path.write_bytes(key_pem)
            ca_path.write_bytes(cert_pem)
            from tigrcorn.config.model import ListenerConfig
            listener = ListenerConfig(
                kind='tcp',
                host='server.example',
                port=443,
                ssl_certfile=str(cert_path),
                ssl_keyfile=str(key_path),
                ssl_ca_certs=str(ca_path),
                ssl_require_client_cert=True,
                alpn_protocols=['h2', 'http/1.1'],
                ocsp_mode='require',
                ocsp_cache_size=33,
                ocsp_max_age=30.0,
                crl_mode='off',
                revocation_fetch=False,
            )
            context = build_server_ssl_context(listener)
        assert context is not None
        self.assertEqual(context.alpn_protocols, ('h2', 'http/1.1'))
        self.assertEqual(context.validation_policy.revocation_mode.value, 'require')
        self.assertIsNone(context.validation_policy.revocation_fetch_policy)


if __name__ == '__main__':
    unittest.main()
