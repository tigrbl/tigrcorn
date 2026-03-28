from __future__ import annotations

import asyncio
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tigrcorn.asgi.send import HTTPResponseCollector, FileBodySegment, materialize_response_body_segments
from tigrcorn.constants import H2_PREFACE
from tigrcorn.http.entity import plan_file_backed_response_entity_semantics
from tigrcorn.http.etag import generate_entity_tag
from tigrcorn.protocols.http2.codec import FrameWriter, serialize_settings
from tigrcorn.protocols.http2.hpack import encode_header_block
from tigrcorn.protocols.http3 import HTTP3ConnectionCore
from tigrcorn.transports.quic import QuicConnection
from tigrcorn.utils.headers import get_header

from tests.test_phase2_entity_semantics_checkpoint import (
    _read_h2_response,
    _read_http1_response,
    _start_server,
)
from tests.test_static_delivery_productionization_checkpoint import (
    _read_h3_response_with_client_progress,
)


class ResponsePipelineStreamingUnitTests(unittest.IsolatedAsyncioTestCase):
    async def test_response_collector_spools_large_body_and_preserves_entity_metadata(self):
        collector = HTTPResponseCollector(spool_threshold=32)
        await collector({'type': 'http.response.start', 'status': 200, 'headers': [(b'content-type', b'text/plain')]})
        await collector({'type': 'http.response.body', 'body': b'a' * 20, 'more_body': True})
        await collector({'type': 'http.response.body', 'body': b'b' * 40, 'more_body': False})
        collector.finalize()

        self.assertTrue(collector.has_spooled_body())
        self.assertEqual(collector.body_length, 60)
        segments = collector.spooled_body_segments()
        self.assertEqual(len(segments), 1)
        self.assertIsInstance(segments[0], FileBodySegment)
        self.assertEqual(segments[0].count, 60)
        self.assertEqual(await materialize_response_body_segments(segments), (b'a' * 20) + (b'b' * 40))
        self.assertTrue(collector.generated_entity_tag().startswith(b'"'))
        collector.cleanup()


class FileBackedEntityPlanningTests(unittest.TestCase):
    def test_file_backed_planning_supports_ranges_conditionals_and_materialization_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = (b'0123456789' * 1024)
            path = Path(tmp) / 'blob.bin'
            path.write_bytes(payload)
            etag = generate_entity_tag(payload)
            headers = [(b'content-type', b'application/octet-stream')]

            ranged = plan_file_backed_response_entity_semantics(
                method='GET',
                request_headers=[(b'range', b'bytes=128-255')],
                response_headers=headers,
                status=200,
                body_path=str(path),
                body_length=len(payload),
                generated_etag=etag,
            )
            self.assertTrue(ranged.use_body_segments)
            self.assertEqual(ranged.status, 206)
            self.assertEqual(get_header(ranged.headers, b'content-range'), f'bytes 128-255/{len(payload)}'.encode('ascii'))

            not_modified = plan_file_backed_response_entity_semantics(
                method='GET',
                request_headers=[(b'if-none-match', etag)],
                response_headers=headers,
                status=200,
                body_path=str(path),
                body_length=len(payload),
                generated_etag=etag,
            )
            self.assertFalse(not_modified.use_body_segments)
            self.assertEqual(not_modified.status, 304)
            self.assertEqual(not_modified.body, b'')

            coded = plan_file_backed_response_entity_semantics(
                method='GET',
                request_headers=[(b'accept-encoding', b'gzip')],
                response_headers=headers,
                status=200,
                body_path=str(path),
                body_length=len(payload),
                generated_etag=etag,
            )
            self.assertTrue(coded.requires_materialization)


class ResponsePipelineStreamingIntegrationTests(unittest.IsolatedAsyncioTestCase):
    PAYLOAD = (b'streaming-response-payload-' * 2048)

    async def _streaming_app(self, scope, receive, send):
        await receive()
        await send({'type': 'http.response.start', 'status': 200, 'headers': [(b'content-type', b'application/octet-stream')]})
        chunk_size = 16384
        for offset in range(0, len(self.PAYLOAD), chunk_size):
            chunk = self.PAYLOAD[offset : offset + chunk_size]
            await send({'type': 'http.response.body', 'body': chunk, 'more_body': offset + chunk_size < len(self.PAYLOAD)})

    async def _assert_streamed_without_materialization(self, *, http_versions: list[str], transport: str = 'tcp') -> tuple[object, int]:
        spool_calls: list[bool] = []
        original_ensure_spool_file = HTTPResponseCollector._ensure_spool_file

        def wrapped_ensure_spool_file(self):
            spool_calls.append(True)
            return original_ensure_spool_file(self)

        async def fail_materialize(self):  # pragma: no cover - exercised only on regression
            raise AssertionError('generic streamed response should not be materialized')

        with (
            patch('tigrcorn.asgi.send.DEFAULT_RESPONSE_BODY_SPOOL_THRESHOLD', 4096),
            patch.object(HTTPResponseCollector, '_ensure_spool_file', wrapped_ensure_spool_file),
            patch.object(HTTPResponseCollector, 'materialize_body', fail_materialize),
        ):
            server, port = await _start_server(self._streaming_app, http_versions=http_versions, transport=transport)
            try:
                if transport == 'udp':
                    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    sock.setblocking(False)
                    client = QuicConnection(is_client=True, secret=b'shared', local_cid=b'cli-step5')
                    core = HTTP3ConnectionCore()
                    loop = asyncio.get_running_loop()
                    try:
                        sock.sendto(client.build_initial(), ('127.0.0.1', port))
                        for _ in range(2):
                            data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 1.0)
                            for event in client.receive_datagram(data):
                                if event.kind == 'stream':
                                    core.receive_stream_data(event.stream_id, event.data, fin=event.fin)
                        request_payload = core.get_request(0).encode_request(
                            [
                                (b':method', b'GET'),
                                (b':scheme', b'https'),
                                (b':path', b'/'),
                                (b':authority', b'localhost'),
                            ],
                            body=b'x' * 6000,
                        )
                        target = ('127.0.0.1', port)
                        sock.sendto(client.send_stream_data(0, request_payload, fin=True), target)
                        response_headers, body = await _read_h3_response_with_client_progress(sock, core, client, target)
                    finally:
                        sock.close()
                elif http_versions == ['2']:
                    reader, writer = await asyncio.open_connection('127.0.0.1', port)
                    try:
                        writer.write(H2_PREFACE)
                        writer.write(serialize_settings({}))
                        frame_writer = FrameWriter()
                        headers = encode_header_block([
                            (b':method', b'GET'),
                            (b':scheme', b'http'),
                            (b':path', b'/'),
                            (b':authority', b'localhost'),
                        ])
                        writer.write(frame_writer.headers(1, headers, end_stream=True))
                        await writer.drain()
                        response_headers, body = await _read_h2_response(reader)
                    finally:
                        writer.close()
                        await writer.wait_closed()
                else:
                    reader, writer = await asyncio.open_connection('127.0.0.1', port)
                    try:
                        writer.write(b'GET / HTTP/1.1\r\nHost: localhost\r\n\r\n')
                        await writer.drain()
                        _head, header_map, body = await _read_http1_response(reader)
                        response_headers = list(header_map.items())
                    finally:
                        writer.close()
                        await writer.wait_closed()

                self.assertEqual(body, self.PAYLOAD)
                self.assertTrue(spool_calls)
                header_map = dict(response_headers)
                self.assertEqual(header_map[b'content-length'], str(len(self.PAYLOAD)).encode('ascii'))
                self.assertIsNotNone(header_map.get(b'etag'))
            finally:
                await server.close()

    async def test_http11_generic_large_response_spools_and_streams_without_materialization(self):
        await self._assert_streamed_without_materialization(http_versions=['1.1'])

    async def test_http2_generic_large_response_spools_and_streams_without_materialization(self):
        await self._assert_streamed_without_materialization(http_versions=['2'])

    async def test_http3_generic_large_response_spools_and_streams_without_materialization(self):
        await self._assert_streamed_without_materialization(http_versions=['3'], transport='udp')


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
