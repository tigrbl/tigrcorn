from __future__ import annotations

import asyncio
import socket
import unittest

from tigrcorn.config.load import build_config
from tigrcorn.config.model import ListenerConfig
from tigrcorn.constants import H2_PREFACE
from tigrcorn.http.early_hints import sanitize_informational_headers
from tigrcorn.protocols.http2.codec import FRAME_DATA, FRAME_HEADERS, FRAME_SETTINGS, FrameBuffer, FrameWriter, decode_settings, serialize_settings
from tigrcorn.protocols.http2.hpack import HPACKDecoder, encode_header_block
from tigrcorn.protocols.http3 import HTTP3ConnectionCore
from tigrcorn.server.runner import TigrCornServer
from tigrcorn.transports.quic import QuicConnection


async def _start_server(app, *, tcp_versions: list[str] | None = None):
    config = build_config(
        host='127.0.0.1',
        port=0,
        lifespan='off',
        http_versions=tcp_versions or ['1.1'],
        quic_secret=b'shared',
    )
    if '3' in (tcp_versions or []):
        config.listeners.clear()
        config.listeners.append(
            ListenerConfig(
                kind='udp',
                host='127.0.0.1',
                port=0,
                http_versions=['3'],
                protocols=['http3'],
                quic_secret=b'shared',
            )
        )
    server = TigrCornServer(app, config)
    await server.start()
    tcp_port = None
    udp_port = None
    for listener in server._listeners:
        if hasattr(listener, 'server') and getattr(listener, 'server', None) is not None:
            sockets = listener.server.sockets or []
            if sockets:
                tcp_port = sockets[0].getsockname()[1]
        if hasattr(listener, 'transport') and getattr(listener, 'transport', None) is not None:
            udp_port = listener.transport.get_extra_info('sockname')[1]
    return server, tcp_port, udp_port


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


async def _read_h2_response_sequence(reader: asyncio.StreamReader) -> tuple[list[list[tuple[bytes, bytes]]], bytes]:
    buf = FrameBuffer()
    decoder = HPACKDecoder()
    header_blocks: list[list[tuple[bytes, bytes]]] = []
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
                header_blocks.append(decoder.decode_header_block(frame.payload))
                if frame.flags & 0x1:
                    ended = True
            elif frame.frame_type == FRAME_DATA:
                body.extend(frame.payload)
                if frame.flags & 0x1:
                    ended = True
        if header_blocks and ended:
            break
    return header_blocks, bytes(body)


async def _prime_http3(sock: socket.socket, client: QuicConnection, core: HTTP3ConnectionCore, *, port: int) -> None:
    loop = asyncio.get_running_loop()
    sock.sendto(client.build_initial(), ('127.0.0.1', port))
    received = 0
    for _ in range(4):
        try:
            data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 1.0)
        except TimeoutError:
            if received:
                break
            raise
        received += 1
        for event in client.receive_datagram(data):
            if event.kind == 'stream':
                core.receive_stream_data(event.stream_id, event.data, fin=event.fin)


async def _read_h3_response_state(sock: socket.socket, client: QuicConnection, core: HTTP3ConnectionCore, *, stream_id: int):
    loop = asyncio.get_running_loop()
    response_state = None
    while response_state is None or not response_state.ended:
        data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 1.0)
        for event in client.receive_datagram(data):
            if event.kind == 'stream':
                state = core.receive_stream_data(event.stream_id, event.data, fin=event.fin)
                if event.stream_id == stream_id:
                    response_state = state
    assert response_state is not None
    return response_state


class RFC8297UnitTests(unittest.TestCase):
    def test_sanitize_103_allows_only_link_and_strips_connection_specific_headers(self):
        headers = sanitize_informational_headers(
            103,
            [
                (b'Link', b'</app.js>; rel=preload; as=script'),
                (b'Connection', b'close'),
                (b'X-Unsafe', b'no'),
                (b'Link', b'</app.js>; rel=preload; as=script'),
            ],
        )
        self.assertEqual(headers, [(b'link', b'</app.js>; rel=preload; as=script')])


class RFC8297IntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_http11_103_is_emitted_before_final_response(self):
        async def app(scope, receive, send):
            await receive()
            await send({'type': 'http.response.start', 'status': 103, 'headers': [(b'link', b'</app.js>; rel=preload; as=script'), (b'x-unsafe', b'no')]})
            await send({'type': 'http.response.start', 'status': 200, 'headers': [(b'content-type', b'text/plain')]})
            await send({'type': 'http.response.body', 'body': b'ok', 'more_body': False})

        server, port, _ = await _start_server(app, tcp_versions=['1.1'])
        try:
            reader, writer = await asyncio.open_connection('127.0.0.1', port)
            writer.write(b'GET / HTTP/1.1\r\nHost: localhost\r\n\r\n')
            await writer.drain()
            interim_head, interim_headers, interim_body = await _read_http1_response(reader)
            self.assertIn(b'103 Early Hints', interim_head)
            self.assertEqual(interim_body, b'')
            self.assertIn(b'link', interim_headers)
            self.assertNotIn(b'x-unsafe', interim_headers)
            final_head, _final_headers, final_body = await _read_http1_response(reader)
            self.assertIn(b'200 OK', final_head)
            self.assertEqual(final_body, b'ok')
            writer.close()
            await writer.wait_closed()
        finally:
            await server.close()

    async def test_http2_103_is_emitted_before_final_headers(self):
        async def app(scope, receive, send):
            await receive()
            await send({'type': 'http.response.start', 'status': 103, 'headers': [(b'link', b'</app.css>; rel=preload; as=style'), (b'x-unsafe', b'no')]})
            await send({'type': 'http.response.start', 'status': 200, 'headers': [(b'content-type', b'text/plain')]})
            await send({'type': 'http.response.body', 'body': b'ok', 'more_body': False})

        server, port, _ = await _start_server(app, tcp_versions=['2'])
        try:
            reader, writer = await asyncio.open_connection('127.0.0.1', port)
            frame_writer = FrameWriter()
            writer.write(H2_PREFACE)
            writer.write(serialize_settings({}))
            request_headers = encode_header_block([
                (b':method', b'GET'),
                (b':scheme', b'http'),
                (b':path', b'/'),
                (b':authority', b'localhost'),
            ])
            writer.write(frame_writer.headers(1, request_headers, end_stream=True))
            await writer.drain()
            header_blocks, body = await _read_h2_response_sequence(reader)
            self.assertGreaterEqual(len(header_blocks), 2)
            self.assertIn((b':status', b'103'), header_blocks[0])
            self.assertIn((b'link', b'</app.css>; rel=preload; as=style'), header_blocks[0])
            self.assertNotIn((b'x-unsafe', b'no'), header_blocks[0])
            self.assertIn((b':status', b'200'), header_blocks[-1])
            self.assertEqual(body, b'ok')
            writer.close()
            await writer.wait_closed()
        finally:
            await server.close()

    async def test_http3_103_is_emitted_before_final_headers(self):
        async def app(scope, receive, send):
            await receive()
            await send({'type': 'http.response.start', 'status': 103, 'headers': [(b'link', b'</app.js>; rel=preload; as=script'), (b'x-unsafe', b'no')]})
            await send({'type': 'http.response.start', 'status': 200, 'headers': [(b'content-type', b'text/plain')]})
            await send({'type': 'http.response.body', 'body': b'ok', 'more_body': False})

        server, _tcp_port, udp_port = await _start_server(app, tcp_versions=['3'])
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setblocking(False)
        client = QuicConnection(is_client=True, secret=b'shared', local_cid=b'rfc8297')
        core = HTTP3ConnectionCore(role='client')
        try:
            await _prime_http3(sock, client, core, port=udp_port)
            request_stream_id = 0
            payload = core.get_request(request_stream_id).encode_request([
                (b':method', b'GET'),
                (b':scheme', b'https'),
                (b':path', b'/'),
                (b':authority', b'localhost'),
            ])
            sock.sendto(client.send_stream_data(request_stream_id, payload, fin=True), ('127.0.0.1', udp_port))
            response_state = await _read_h3_response_state(sock, client, core, stream_id=request_stream_id)
            self.assertEqual(len(response_state.informational_headers), 1)
            self.assertIn((b':status', b'103'), response_state.informational_headers[0])
            self.assertIn((b'link', b'</app.js>; rel=preload; as=script'), response_state.informational_headers[0])
            self.assertNotIn((b'x-unsafe', b'no'), response_state.informational_headers[0])
            self.assertIn((b':status', b'200'), response_state.headers)
            self.assertEqual(response_state.body, b'ok')
        finally:
            sock.close()
            await server.close()


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
