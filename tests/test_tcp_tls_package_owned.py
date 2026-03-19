from __future__ import annotations

import asyncio
import contextlib
import ssl
import unittest
from pathlib import Path

from tigrcorn.config.load import build_config
from tigrcorn.constants import H2_PREFACE
from tigrcorn.protocols.http2.codec import (
    FRAME_DATA,
    FRAME_HEADERS,
    FRAME_SETTINGS,
    FRAME_WINDOW_UPDATE,
    FrameBuffer,
    FrameWriter,
    decode_settings,
    serialize_frame,
    serialize_settings,
)
from tigrcorn.protocols.http2.hpack import decode_header_block, encode_header_block
from tigrcorn.server.runner import TigrCornServer

ROOT = Path(__file__).resolve().parent
CERTS = ROOT / 'fixtures_certs'
SERVER_CERT = CERTS / 'interop-localhost-cert.pem'
SERVER_KEY = CERTS / 'interop-localhost-key.pem'
CLIENT_CERT = CERTS / 'interop-client-cert.pem'
CLIENT_KEY = CERTS / 'interop-client-key.pem'


async def _start_tls_server(app, *, http_versions: list[str] | None = None, ssl_ca_certs: str | None = None, require_client_cert: bool = False):
    config = build_config(
        host='127.0.0.1',
        port=0,
        lifespan='off',
        http_versions=http_versions or ['1.1'],
        ssl_certfile=str(SERVER_CERT),
        ssl_keyfile=str(SERVER_KEY),
        ssl_ca_certs=ssl_ca_certs,
        ssl_require_client_cert=require_client_cert,
    )
    server = TigrCornServer(app, config)
    await server.start()
    listener = server._listeners[0]
    port = listener.server.sockets[0].getsockname()[1]
    return server, port


def _client_context(*, alpn: list[str], with_client_cert: bool = False) -> ssl.SSLContext:
    context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=str(SERVER_CERT))
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    context.set_alpn_protocols(alpn)
    if with_client_cert:
        context.load_cert_chain(str(CLIENT_CERT), str(CLIENT_KEY))
    return context


class PackageOwnedTCPTLSTests(unittest.IsolatedAsyncioTestCase):
    async def test_http11_over_package_owned_tls_exposes_tls_extension(self):
        seen = {}

        async def app(scope, receive, send):
            seen['scope'] = scope
            event = await receive()
            await send({'type': 'http.response.start', 'status': 200, 'headers': [(b'content-type', b'text/plain')]})
            await send({'type': 'http.response.body', 'body': event['body'], 'more_body': False})

        server, port = await _start_tls_server(app, http_versions=['1.1'])
        try:
            reader, writer = await asyncio.open_connection(
                '127.0.0.1',
                port,
                ssl=_client_context(alpn=['http/1.1']),
                server_hostname='localhost',
            )
            writer.write(b'POST /tls HTTP/1.1\r\nHost: localhost\r\nContent-Length: 5\r\n\r\nhello')
            await writer.drain()
            data = await reader.read(65535)
            self.assertIn(b'200 OK', data)
            self.assertTrue(data.endswith(b'hello'))
            tls_ext = seen['scope']['extensions']['tls']
            self.assertEqual(tls_ext['selected_alpn_protocol'], 'http/1.1')
            self.assertNotIn('peer_cert', tls_ext)
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()
        finally:
            await server.close()

    async def test_mtls_over_package_owned_tls_exposes_client_peer_certificate(self):
        seen = {}

        async def app(scope, receive, send):
            seen['scope'] = scope
            await receive()
            await send({'type': 'http.response.start', 'status': 204, 'headers': []})
            await send({'type': 'http.response.body', 'body': b'', 'more_body': False})

        server, port = await _start_tls_server(
            app,
            http_versions=['1.1'],
            ssl_ca_certs=str(CLIENT_CERT),
            require_client_cert=True,
        )
        try:
            reader, writer = await asyncio.open_connection(
                '127.0.0.1',
                port,
                ssl=_client_context(alpn=['http/1.1'], with_client_cert=True),
                server_hostname='localhost',
            )
            writer.write(b'POST /mtls HTTP/1.1\r\nHost: localhost\r\nContent-Length: 0\r\n\r\n')
            await writer.drain()
            data = await reader.read(65535)
            self.assertIn(b'204 No Content', data)
            tls_ext = seen['scope']['extensions']['tls']
            self.assertEqual(tls_ext['selected_alpn_protocol'], 'http/1.1')
            self.assertIn('peer_cert', tls_ext)
            self.assertIn('interop-client', tls_ext['peer_cert']['subject'])
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()
        finally:
            await server.close()

    async def test_http2_over_package_owned_tls_negotiates_h2(self):
        seen = {}

        async def app(scope, receive, send):
            seen['scope'] = scope
            event = await receive()
            await send({'type': 'http.response.start', 'status': 200, 'headers': [(b'content-type', b'text/plain')]})
            await send({'type': 'http.response.body', 'body': event['body'], 'more_body': False})

        server, port = await _start_tls_server(app, http_versions=['2'])
        try:
            reader, writer = await asyncio.open_connection(
                '127.0.0.1',
                port,
                ssl=_client_context(alpn=['h2']),
                server_hostname='localhost',
            )
            writer.write(H2_PREFACE)
            writer.write(serialize_settings({}))
            request_headers = encode_header_block([
                (b':method', b'POST'),
                (b':path', b'/h2-tls'),
                (b':scheme', b'https'),
                (b':authority', b'localhost'),
                (b'content-length', b'5'),
            ])
            frame_writer = FrameWriter()
            writer.write(frame_writer.headers(1, request_headers, end_stream=False))
            writer.write(frame_writer.data(1, b'hello', end_stream=True))
            await writer.drain()

            buf = FrameBuffer()
            response_headers = []
            body = bytearray()
            ended = False
            saw_settings = False
            while not ended:
                data = await reader.read(65535)
                self.assertTrue(data)
                buf.feed(data)
                for frame in buf.pop_all():
                    if frame.frame_type == FRAME_SETTINGS:
                        if frame.payload:
                            _ = decode_settings(frame.payload)
                        saw_settings = True
                    elif frame.frame_type == FRAME_HEADERS:
                        response_headers.extend(decode_header_block(frame.payload))
                        if frame.flags & 0x1:
                            ended = True
                    elif frame.frame_type == FRAME_DATA:
                        body.extend(frame.payload)
                        writer.write(serialize_frame(FRAME_WINDOW_UPDATE, 0, 0, len(frame.payload).to_bytes(4, 'big')))
                        writer.write(serialize_frame(FRAME_WINDOW_UPDATE, 0, frame.stream_id, len(frame.payload).to_bytes(4, 'big')))
                        await writer.drain()
                        if frame.flags & 0x1:
                            ended = True
            self.assertTrue(saw_settings)
            self.assertIn((b':status', b'200'), response_headers)
            self.assertEqual(bytes(body), b'hello')
            tls_ext = seen['scope']['extensions']['tls']
            self.assertEqual(tls_ext['selected_alpn_protocol'], 'h2')
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()
        finally:
            await server.close()


if __name__ == '__main__':
    unittest.main()
