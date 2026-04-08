from __future__ import annotations

import asyncio
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tigrcorn.constants import H2_PREFACE
from tigrcorn.protocols.http2.codec import FrameWriter, serialize_settings
from tigrcorn.protocols.http2.hpack import encode_header_block
from tigrcorn.protocols.http3 import HTTP3ConnectionCore
from tigrcorn.static import StaticFilesApp
from tigrcorn.transports.quic import QuicConnection

from tests.test_phase2_entity_semantics_checkpoint import (
    _read_h2_response,
    _read_http1_response,
    _start_server,
    _workspace_tempdir,
)


async def _read_h3_response_with_client_progress(
    sock: socket.socket,
    core: HTTP3ConnectionCore,
    client: QuicConnection,
    addr: tuple[str, int],
) -> tuple[list[tuple[bytes, bytes]], bytes]:
    """Read a streamed HTTP/3 response while driving client ACK/timer progress.

    Large HTTP/3 responses are subject to QUIC anti-amplification and recovery pacing.
    The checkpoint server path relies on normal client progress signals, so the test
    pumps scheduled client ACK/timer datagrams back to the server while the response
    body is streaming.
    """
    loop = asyncio.get_running_loop()
    response_state = None
    for _ in range(128):
        data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 2.0)
        for event in client.receive_datagram(data):
            if event.kind == 'stream' and event.stream_id == 0:
                response_state = core.receive_stream_data(event.stream_id, event.data, fin=event.fin)
        for raw in client.take_handshake_datagrams() + client.drain_scheduled_datagrams():
            sock.sendto(raw, addr)
        if response_state is not None and response_state.ended:
            return response_state.headers, response_state.body
    raise AssertionError('timed out waiting for full HTTP/3 response body')


class StaticDeliveryProductionizationTests(unittest.IsolatedAsyncioTestCase):
    async def test_static_files_app_uses_streaming_file_extension_when_available(self):
        async def receive() -> dict:
            return {'type': 'http.request', 'body': b'', 'more_body': False}

        sent: list[dict] = []

        async def send(message: dict) -> None:
            sent.append(message)

        with _workspace_tempdir() as root:
            payload = (b'0123456789abcdef' * 65536)
            (root / 'blob.bin').write_bytes(payload)
            app = StaticFilesApp(root)
            scope = {
                'type': 'http',
                'method': 'GET',
                'path': '/blob.bin',
                'headers': [],
                'extensions': {'tigrcorn.http.response.file': {'protocol': 'http/1.1', 'streaming': True, 'sendfile': True}},
            }
            with patch('pathlib.Path.read_bytes', side_effect=AssertionError('read_bytes must not be used for streaming static delivery')):
                await app(scope, receive, send)
            self.assertEqual(sent[0]['type'], 'http.response.start')
            self.assertEqual(sent[0]['status'], 200)
            self.assertEqual(sent[1]['type'], 'tigrcorn.http.response.file')
            self.assertEqual(sent[1]['segments'][0]['type'], 'file')
            self.assertEqual(sent[1]['segments'][0]['path'], str(root / 'blob.bin'))
            self.assertEqual(sent[1]['segments'][0]['offset'], 0)
            self.assertEqual(sent[1]['segments'][0]['count'], len(payload))

    async def test_http11_large_static_file_serves_without_read_bytes(self):
        with _workspace_tempdir() as root:
            payload = (b'http11-static-' * 131072)
            (root / 'blob.bin').write_bytes(payload)
            app = StaticFilesApp(root)
            server, port = await _start_server(app, http_versions=['1.1'])
            try:
                with patch('pathlib.Path.read_bytes', side_effect=AssertionError('read_bytes must not be used for HTTP/1.1 static delivery')):
                    reader, writer = await asyncio.open_connection('127.0.0.1', port)
                    writer.write(b'GET /blob.bin HTTP/1.1\r\nHost: localhost\r\n\r\n')
                    await writer.drain()
                    _head, headers, body = await _read_http1_response(reader)
                    self.assertEqual(headers[b'content-length'], str(len(payload)).encode('ascii'))
                    self.assertEqual(body, payload)
                    writer.close()
                    await writer.wait_closed()
            finally:
                await server.close()

    async def test_http2_large_static_range_serves_without_read_bytes(self):
        with _workspace_tempdir() as root:
            payload = (b'http2-static-range-' * 131072)
            (root / 'blob.bin').write_bytes(payload)
            app = StaticFilesApp(root)
            server, port = await _start_server(app, http_versions=['2'])
            try:
                with patch('pathlib.Path.read_bytes', side_effect=AssertionError('read_bytes must not be used for HTTP/2 static delivery')):
                    reader, writer = await asyncio.open_connection('127.0.0.1', port)
                    writer.write(H2_PREFACE)
                    writer.write(serialize_settings({}))
                    headers = encode_header_block([
                        (b':method', b'GET'),
                        (b':scheme', b'http'),
                        (b':path', b'/blob.bin'),
                        (b':authority', b'localhost'),
                        (b'range', b'bytes=4096-8191'),
                    ])
                    frame_writer = FrameWriter()
                    writer.write(frame_writer.headers(1, headers, end_stream=True))
                    await writer.drain()
                    response_headers, body = await _read_h2_response(reader)
                    header_map = dict(response_headers)
                    self.assertEqual(header_map[b':status'], b'206')
                    self.assertEqual(header_map[b'content-range'], f'bytes 4096-8191/{len(payload)}'.encode('ascii'))
                    self.assertEqual(body, payload[4096:8192])
                    writer.close()
                    await writer.wait_closed()
            finally:
                await server.close()

    async def test_http3_large_static_range_serves_without_read_bytes(self):
        with _workspace_tempdir() as root:
            payload = (b'http3-static-range-' * 131072)
            (root / 'blob.bin').write_bytes(payload)
            app = StaticFilesApp(root)
            server, port = await _start_server(app, http_versions=['3'], transport='udp')
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setblocking(False)
            client = QuicConnection(is_client=True, secret=b'shared', local_cid=b'cli-static')
            core = HTTP3ConnectionCore()
            loop = asyncio.get_running_loop()
            try:
                with patch('pathlib.Path.read_bytes', side_effect=AssertionError('read_bytes must not be used for HTTP/3 static delivery')):
                    sock.sendto(client.build_initial(), ('127.0.0.1', port))
                    for _ in range(2):
                        data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 1.0)
                        for event in client.receive_datagram(data):
                            if event.kind == 'stream':
                                core.receive_stream_data(event.stream_id, event.data, fin=event.fin)

                    request_payload = core.get_request(0).encode_request([
                        (b':method', b'GET'),
                        (b':scheme', b'https'),
                        (b':path', b'/blob.bin'),
                        (b':authority', b'localhost'),
                        (b'range', b'bytes=16384-32767'),
                    ], body=b'x' * 6000)
                    target = ('127.0.0.1', port)
                    sock.sendto(client.send_stream_data(0, request_payload, fin=True), target)
                    response_headers, body = await _read_h3_response_with_client_progress(sock, core, client, target)
                    header_map = dict(response_headers)
                    self.assertEqual(header_map[b':status'], b'206')
                    self.assertEqual(header_map[b'content-range'], f'bytes 16384-32767/{len(payload)}'.encode('ascii'))
                    self.assertEqual(body, payload[16384:32768])
            finally:
                sock.close()
                await server.close()


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
