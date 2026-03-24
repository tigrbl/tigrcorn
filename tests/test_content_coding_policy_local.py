from __future__ import annotations

import asyncio
import socket
import unittest

from tigrcorn.config.load import build_config
from tigrcorn.constants import H2_PREFACE
from tigrcorn.protocols.http2.codec import FRAME_DATA, FRAME_HEADERS, FRAME_SETTINGS, FrameBuffer, FrameWriter, decode_settings, serialize_settings
from tigrcorn.protocols.http2.hpack import decode_header_block, encode_header_block
from tigrcorn.protocols.http3 import HTTP3ConnectionCore
from tigrcorn.server.runner import TigrCornServer
from tigrcorn.transports.quic import QuicConnection


async def _start_server(*, http_versions: list[str], policy: str, transport: str = 'tcp'):
    async def app(scope, receive, send):
        await send({'type': 'http.response.start', 'status': 200, 'headers': [(b'content-type', b'text/plain; charset=utf-8')]})
        await send({'type': 'http.response.body', 'body': b'compress-me', 'more_body': False})

    kwargs = {'host': '127.0.0.1', 'port': 0, 'lifespan': 'off', 'http_versions': http_versions, 'config': {'http': {'content_coding_policy': policy}}}
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


async def _read_http1_response(reader: asyncio.StreamReader) -> tuple[bytes, bytes]:
    head = await reader.readuntil(b'\r\n\r\n')
    headers = {}
    for line in head.split(b'\r\n')[1:]:
        if not line:
            continue
        name, value = line.split(b':', 1)
        headers[name.strip().lower()] = value.strip()
    length = int(headers.get(b'content-length', b'0'))
    body = await reader.readexactly(length) if length else b''
    return head, body


class ContentCodingPolicyLocalTests(unittest.IsolatedAsyncioTestCase):
    async def test_http11_identity_only_forbidden_returns_406(self):
        server, port = await _start_server(http_versions=['1.1'], policy='identity-only')
        try:
            reader, writer = await asyncio.open_connection('127.0.0.1', port)
            writer.write(
                b'GET / HTTP/1.1\r\n'
                b'Host: localhost\r\n'
                b'Accept-Encoding: identity;q=0,*;q=0\r\n\r\n'
            )
            await writer.drain()
            head, body = await _read_http1_response(reader)
            self.assertIn(b' 406 ', head)
            self.assertIn(b'vary: accept-encoding', head.lower())
            self.assertEqual(body, b'not acceptable')
            writer.close(); await writer.wait_closed()
        finally:
            await server.close()

    async def test_http11_strict_unsupported_encoding_returns_406(self):
        server, port = await _start_server(http_versions=['1.1'], policy='strict')
        try:
            reader, writer = await asyncio.open_connection('127.0.0.1', port)
            writer.write(
                b'GET / HTTP/1.1\r\n'
                b'Host: localhost\r\n'
                b'Accept-Encoding: zstd\r\n\r\n'
            )
            await writer.drain()
            head, body = await _read_http1_response(reader)
            self.assertIn(b' 406 ', head)
            self.assertIn(b'vary: accept-encoding', head.lower())
            self.assertEqual(body, b'not acceptable')
            writer.close(); await writer.wait_closed()
        finally:
            await server.close()

    async def test_http2_identity_only_forbidden_returns_406(self):
        server, port = await _start_server(http_versions=['2'], policy='identity-only')
        try:
            reader, writer = await asyncio.open_connection('127.0.0.1', port)
            writer.write(H2_PREFACE)
            writer.write(serialize_settings({}))
            headers = encode_header_block([
                (b':method', b'GET'),
                (b':scheme', b'http'),
                (b':path', b'/'),
                (b':authority', b'localhost'),
                (b'accept-encoding', b'identity;q=0,*;q=0'),
            ])
            frame_writer = FrameWriter()
            writer.write(frame_writer.headers(1, headers, end_stream=True))
            await writer.drain()
            buf = FrameBuffer(); response_headers=[]; body=bytearray(); ended=False
            while not ended:
                data = await asyncio.wait_for(reader.read(65535), 2.0)
                self.assertTrue(data)
                buf.feed(data)
                for frame in buf.pop_all():
                    if frame.frame_type == FRAME_SETTINGS:
                        if frame.payload:
                            decode_settings(frame.payload)
                    elif frame.frame_type == FRAME_HEADERS:
                        response_headers.extend(decode_header_block(frame.payload))
                        if frame.flags & 0x1:
                            ended = True
                    elif frame.frame_type == FRAME_DATA:
                        body.extend(frame.payload)
                        if frame.flags & 0x1:
                            ended = True
                if response_headers and ended:
                    break
            self.assertIn((b':status', b'406'), response_headers)
            self.assertIn((b'vary', b'accept-encoding'), response_headers)
            self.assertEqual(bytes(body), b'not acceptable')
            writer.close(); await writer.wait_closed()
        finally:
            await server.close()

    async def test_http2_strict_unsupported_encoding_returns_406(self):
        server, port = await _start_server(http_versions=['2'], policy='strict')
        try:
            reader, writer = await asyncio.open_connection('127.0.0.1', port)
            writer.write(H2_PREFACE)
            writer.write(serialize_settings({}))
            headers = encode_header_block([
                (b':method', b'GET'),
                (b':scheme', b'http'),
                (b':path', b'/'),
                (b':authority', b'localhost'),
                (b'accept-encoding', b'zstd'),
            ])
            frame_writer = FrameWriter()
            writer.write(frame_writer.headers(1, headers, end_stream=True))
            await writer.drain()
            buf = FrameBuffer(); response_headers=[]; body=bytearray(); ended=False
            while not ended:
                data = await asyncio.wait_for(reader.read(65535), 2.0)
                self.assertTrue(data)
                buf.feed(data)
                for frame in buf.pop_all():
                    if frame.frame_type == FRAME_SETTINGS:
                        if frame.payload:
                            decode_settings(frame.payload)
                    elif frame.frame_type == FRAME_HEADERS:
                        response_headers.extend(decode_header_block(frame.payload))
                        if frame.flags & 0x1:
                            ended = True
                    elif frame.frame_type == FRAME_DATA:
                        body.extend(frame.payload)
                        if frame.flags & 0x1:
                            ended = True
                if response_headers and ended:
                    break
            self.assertIn((b':status', b'406'), response_headers)
            self.assertIn((b'vary', b'accept-encoding'), response_headers)
            self.assertEqual(bytes(body), b'not acceptable')
            writer.close(); await writer.wait_closed()
        finally:
            await server.close()

    async def test_http3_identity_only_forbidden_returns_406(self):
        server, port = await _start_server(http_versions=['3'], policy='identity-only', transport='udp')
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setblocking(False)
        client = QuicConnection(is_client=True, secret=b'shared', local_cid=b'cli-identity')
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
                (b':path', b'/'),
                (b':authority', b'localhost'),
                (b'accept-encoding', b'identity;q=0,*;q=0'),
            ])
            sock.sendto(client.send_stream_data(0, request_payload, fin=True), ('127.0.0.1', port))
            response_state = None
            while response_state is None or not response_state.ended:
                data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 1.0)
                for event in client.receive_datagram(data):
                    if event.kind == 'stream' and event.stream_id == 0:
                        response_state = core.receive_stream_data(event.stream_id, event.data, fin=event.fin)
            assert response_state is not None
            self.assertIn((b':status', b'406'), response_state.headers)
            self.assertIn((b'vary', b'accept-encoding'), response_state.headers)
            self.assertEqual(response_state.body, b'not acceptable')
        finally:
            sock.close(); await server.close()

    async def test_http3_strict_unsupported_encoding_returns_406(self):
        server, port = await _start_server(http_versions=['3'], policy='strict', transport='udp')
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setblocking(False)
        client = QuicConnection(is_client=True, secret=b'shared', local_cid=b'cli-strict')
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
                (b':path', b'/'),
                (b':authority', b'localhost'),
                (b'accept-encoding', b'zstd'),
            ])
            sock.sendto(client.send_stream_data(0, request_payload, fin=True), ('127.0.0.1', port))
            response_state = None
            while response_state is None or not response_state.ended:
                data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 1.0)
                for event in client.receive_datagram(data):
                    if event.kind == 'stream' and event.stream_id == 0:
                        response_state = core.receive_stream_data(event.stream_id, event.data, fin=event.fin)
            assert response_state is not None
            self.assertIn((b':status', b'406'), response_state.headers)
            self.assertIn((b'vary', b'accept-encoding'), response_state.headers)
            self.assertEqual(response_state.body, b'not acceptable')
        finally:
            sock.close(); await server.close()


if __name__ == '__main__':
    unittest.main()
