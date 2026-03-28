from __future__ import annotations

import asyncio
import socket
import tempfile
import unittest
from email.utils import formatdate
from pathlib import Path

from tigrcorn.config.load import build_config
from tigrcorn.constants import H2_PREFACE
from tigrcorn.http.conditional import apply_conditional_request
from tigrcorn.http.entity import apply_response_entity_semantics
from tigrcorn.http.etag import generate_entity_tag, parse_entity_tag, strong_compare
from tigrcorn.http.range import apply_byte_ranges
from tigrcorn.protocols.http2.codec import FRAME_DATA, FRAME_HEADERS, FRAME_SETTINGS, FrameBuffer, FrameWriter, decode_settings, serialize_settings
from tigrcorn.protocols.http2.hpack import decode_header_block, encode_header_block
from tigrcorn.protocols.http3 import HTTP3ConnectionCore
from tigrcorn.server.runner import TigrCornServer
from tigrcorn.static import StaticFilesApp
from tigrcorn.transports.quic import QuicConnection
from tigrcorn.utils.headers import get_header


async def _start_server(app, *, http_versions: list[str], transport: str = 'tcp'):
    kwargs = {'host': '127.0.0.1', 'port': 0, 'lifespan': 'off', 'http_versions': http_versions}
    if transport == 'udp':
        kwargs.update({'transport': 'udp', 'protocols': ['http3'], 'quic_secret': b'shared'})
    config = build_config(**kwargs)
    server = TigrCornServer(app, config)
    await server.start()
    if transport == 'udp':
        port = server._listeners[0].transport.get_extra_info('sockname')[1]
    else:
        port = server._listeners[0].server.sockets[0].getsockname()[1]
    return server, port


async def _read_http1_response(reader: asyncio.StreamReader) -> tuple[bytes, dict[bytes, bytes], bytes]:
    head = await reader.readuntil(b'\r\n\r\n')
    headers: dict[bytes, bytes] = {}
    for line in head.split(b'\r\n')[1:]:
        if not line:
            continue
        name, value = line.split(b':', 1)
        headers[name.strip().lower()] = value.strip()
    length = int(headers.get(b'content-length', b'0'))
    body = await reader.readexactly(length) if length else b''
    return head, headers, body


async def _read_h2_response(reader: asyncio.StreamReader) -> tuple[list[tuple[bytes, bytes]], bytes]:
    buf = FrameBuffer()
    headers: list[tuple[bytes, bytes]] = []
    body = bytearray()
    ended = False
    while not ended:
        data = await asyncio.wait_for(reader.read(65535), 2.0)
        assert data
        buf.feed(data)
        for frame in buf.pop_all():
            if frame.frame_type == FRAME_SETTINGS and frame.payload:
                decode_settings(frame.payload)
            elif frame.frame_type == FRAME_HEADERS:
                headers.extend(decode_header_block(frame.payload))
                if frame.flags & 0x1:
                    ended = True
            elif frame.frame_type == FRAME_DATA:
                body.extend(frame.payload)
                if frame.flags & 0x1:
                    ended = True
        if headers and ended:
            break
    return headers, bytes(body)


async def _read_h3_response(sock: socket.socket, core: HTTP3ConnectionCore, client: QuicConnection) -> tuple[list[tuple[bytes, bytes]], bytes]:
    loop = asyncio.get_running_loop()
    response_state = None
    while response_state is None or not response_state.ended:
        data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 1.0)
        for event in client.receive_datagram(data):
            if event.kind == 'stream' and event.stream_id == 0:
                response_state = core.receive_stream_data(event.stream_id, event.data, fin=event.fin)
    assert response_state is not None
    return response_state.headers, response_state.body


class Phase2EntitySemanticsUnitTests(unittest.TestCase):
    def test_generated_etag_parses_and_strong_matches(self):
        tag = generate_entity_tag(b'hello world')
        parsed = parse_entity_tag(tag)
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertTrue(strong_compare(parsed, parse_entity_tag(tag)))

    def test_conditional_engine_supports_if_none_match_if_match_and_dates(self):
        etag = generate_entity_tag(b'payload')
        last_modified = formatdate(1_700_000_000, usegmt=True).encode('ascii')

        not_modified = apply_conditional_request(
            method='GET',
            request_headers=[(b'if-none-match', etag)],
            response_headers=[(b'etag', etag), (b'last-modified', last_modified)],
            body=b'payload',
            status=200,
        )
        self.assertEqual(not_modified.status, 304)
        self.assertEqual(not_modified.body, b'')

        precondition_failed = apply_conditional_request(
            method='PUT',
            request_headers=[(b'if-match', b'"other"')],
            response_headers=[(b'etag', etag), (b'last-modified', last_modified)],
            body=b'payload',
            status=200,
        )
        self.assertEqual(precondition_failed.status, 412)

        ims = apply_conditional_request(
            method='GET',
            request_headers=[(b'if-modified-since', last_modified)],
            response_headers=[(b'last-modified', last_modified)],
            body=b'payload',
            status=200,
        )
        self.assertEqual(ims.status, 304)

        ius = apply_conditional_request(
            method='GET',
            request_headers=[(b'if-unmodified-since', formatdate(1_699_999_000, usegmt=True).encode('ascii'))],
            response_headers=[(b'last-modified', last_modified)],
            body=b'payload',
            status=200,
        )
        self.assertEqual(ius.status, 412)

    def test_range_engine_supports_single_multi_and_unsatisfied_ranges(self):
        body = b'hello world'
        headers = [(b'content-type', b'text/plain')]

        single = apply_byte_ranges(
            method='GET',
            request_headers=[(b'range', b'bytes=0-4')],
            response_headers=headers,
            body=body,
            status=200,
        )
        self.assertEqual(single.status, 206)
        self.assertEqual(single.body, b'hello')
        self.assertEqual(get_header(single.headers, b'content-range'), b'bytes 0-4/11')

        multi = apply_byte_ranges(
            method='GET',
            request_headers=[(b'range', b'bytes=0-1,6-10')],
            response_headers=headers,
            body=body,
            status=200,
        )
        self.assertEqual(multi.status, 206)
        self.assertIn(b'multipart/byteranges', get_header(multi.headers, b'content-type') or b'')
        self.assertIn(b'Content-Range: bytes 0-1/11', multi.body)
        self.assertIn(b'Content-Range: bytes 6-10/11', multi.body)

        unsatisfied = apply_byte_ranges(
            method='GET',
            request_headers=[(b'range', b'bytes=40-50')],
            response_headers=headers,
            body=body,
            status=200,
        )
        self.assertEqual(unsatisfied.status, 416)
        self.assertEqual(get_header(unsatisfied.headers, b'content-range'), b'bytes */11')

    def test_entity_semantics_head_and_range_interactions(self):
        head = apply_response_entity_semantics(
            method='HEAD',
            request_headers=[],
            response_headers=[(b'content-type', b'text/plain')],
            body=b'hello',
            status=200,
            apply_content_coding=False,
        )
        self.assertEqual(head.body, b'')
        self.assertEqual(get_header(head.headers, b'content-length'), b'5')
        self.assertIsNotNone(get_header(head.headers, b'etag'))

        partial = apply_response_entity_semantics(
            method='GET',
            request_headers=[(b'range', b'bytes=0-4'), (b'accept-encoding', b'gzip')],
            response_headers=[(b'content-type', b'text/plain')],
            body=b'hello world',
            status=200,
            apply_content_coding=True,
        )
        self.assertEqual(partial.status, 206)
        self.assertEqual(partial.body, b'hello')
        self.assertIsNone(get_header(partial.headers, b'content-encoding'))


class StaticFilesPhase2Tests(unittest.IsolatedAsyncioTestCase):
    async def test_static_files_app_supports_etag_conditionals_and_ranges(self):
        async def receive() -> dict:
            return {'type': 'http.request', 'body': b'', 'more_body': False}

        sent: list[dict] = []

        async def send(message: dict) -> None:
            sent.append(message)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'hello.txt').write_text('hello world', encoding='utf-8')
            app = StaticFilesApp(root)

            await app({'type': 'http', 'method': 'GET', 'path': '/hello.txt', 'headers': [(b'range', b'bytes=0-4')]}, receive, send)
            self.assertEqual(sent[0]['status'], 206)
            headers = dict(sent[0]['headers'])
            self.assertEqual(headers[b'content-range'], b'bytes 0-4/11')
            self.assertEqual(sent[1]['body'], b'hello')
            etag = headers[b'etag']

            sent.clear()
            await app({'type': 'http', 'method': 'GET', 'path': '/hello.txt', 'headers': [(b'if-none-match', etag)]}, receive, send)
            self.assertEqual(sent[0]['status'], 304)
            self.assertEqual(sent[1]['body'], b'')


class Phase2EntitySemanticsIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_http11_generates_etag_and_honors_if_none_match(self):
        async def app(scope, receive, send):
            await receive()
            await send({'type': 'http.response.start', 'status': 200, 'headers': [(b'content-type', b'text/plain')]})
            await send({'type': 'http.response.body', 'body': b'entity-body', 'more_body': False})

        server, port = await _start_server(app, http_versions=['1.1'])
        try:
            reader, writer = await asyncio.open_connection('127.0.0.1', port)
            writer.write(b'GET / HTTP/1.1\r\nHost: localhost\r\n\r\n')
            await writer.drain()
            _head, headers, body = await _read_http1_response(reader)
            self.assertEqual(body, b'entity-body')
            etag = headers[b'etag']
            writer.close()
            await writer.wait_closed()

            reader, writer = await asyncio.open_connection('127.0.0.1', port)
            writer.write(b'GET / HTTP/1.1\r\nHost: localhost\r\nIf-None-Match: ' + etag + b'\r\n\r\n')
            await writer.drain()
            _head, headers, body = await _read_http1_response(reader)
            self.assertEqual(headers.get(b'content-length', b'0'), b'0')
            self.assertEqual(body, b'')
            writer.close()
            await writer.wait_closed()
        finally:
            await server.close()

    async def test_http2_head_preserves_content_length_and_suppresses_body(self):
        async def app(scope, receive, send):
            await receive()
            await send({'type': 'http.response.start', 'status': 200, 'headers': [(b'content-type', b'text/plain')]})
            await send({'type': 'http.response.body', 'body': b'hello', 'more_body': False})

        server, port = await _start_server(app, http_versions=['2'])
        try:
            reader, writer = await asyncio.open_connection('127.0.0.1', port)
            writer.write(H2_PREFACE)
            writer.write(serialize_settings({}))
            headers = encode_header_block([
                (b':method', b'HEAD'),
                (b':scheme', b'http'),
                (b':path', b'/'),
                (b':authority', b'localhost'),
            ])
            frame_writer = FrameWriter()
            writer.write(frame_writer.headers(1, headers, end_stream=True))
            await writer.drain()
            response_headers, body = await _read_h2_response(reader)
            self.assertIn((b'content-length', b'5'), response_headers)
            self.assertEqual(body, b'')
            self.assertIsNotNone(dict(response_headers).get(b'etag'))
            writer.close()
            await writer.wait_closed()
        finally:
            await server.close()

    async def test_http3_range_request_returns_partial_response(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'hello.txt').write_text('hello world', encoding='utf-8')
            app = StaticFilesApp(root)
            server, port = await _start_server(app, http_versions=['3'], transport='udp')
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setblocking(False)
            client = QuicConnection(is_client=True, secret=b'shared', local_cid=b'cli-range')
            core = HTTP3ConnectionCore()
            loop = asyncio.get_running_loop()
            try:
                sock.sendto(client.build_initial(), ('127.0.0.1', port))
                for _ in range(2):
                    data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 1.0)
                    for event in client.receive_datagram(data):
                        if event.kind == 'stream':
                            core.receive_stream_data(event.stream_id, event.data, fin=event.fin)

                request_payload = core.get_request(0).encode_request([
                    (b':method', b'GET'),
                    (b':scheme', b'https'),
                    (b':path', b'/hello.txt'),
                    (b':authority', b'localhost'),
                    (b'range', b'bytes=6-10'),
                ])
                sock.sendto(client.send_stream_data(0, request_payload, fin=True), ('127.0.0.1', port))
                response_headers, body = await _read_h3_response(sock, core, client)
                self.assertIn((b':status', b'206'), response_headers)
                self.assertIn((b'content-range', b'bytes 6-10/11'), response_headers)
                self.assertEqual(body, b'world')
            finally:
                sock.close()
                await server.close()


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
