
from __future__ import annotations

import asyncio
import unittest

from tigrcorn.config.load import build_config
from tigrcorn.constants import H2_PREFACE
from tigrcorn.observability.logging import AccessLogger, configure_logging
from tigrcorn.protocols.http2.codec import (
    FLAG_END_HEADERS,
    FLAG_END_STREAM,
    FRAME_DATA,
    FRAME_HEADERS,
    FRAME_PUSH_PROMISE,
    FRAME_SETTINGS,
    FrameBuffer,
    FrameWriter,
    HTTP2Frame,
    parse_push_promise,
    serialize_settings,
    SETTING_ENABLE_PUSH,
)
from tigrcorn.protocols.http2.hpack import HPACKDecoder, HPACKEncoder
from tigrcorn.server.runner import TigrCornServer


async def _start_http2_server(app):
    config = build_config(host='127.0.0.1', port=0, lifespan='off', http_versions=['2'])
    server = TigrCornServer(app, config)
    await server.start()
    port = server._listeners[0].server.sockets[0].getsockname()[1]
    return server, port


def _request_headers(path: bytes) -> bytes:
    encoder = HPACKEncoder()
    return encoder.encode_header_block([
        (b':method', b'GET'),
        (b':path', path),
        (b':scheme', b'http'),
        (b':authority', b'example'),
    ])


async def _collect_frames(reader: asyncio.StreamReader, *, need_push: bool) -> list[HTTP2Frame]:
    buffer = FrameBuffer()
    frames: list[HTTP2Frame] = []
    deadline = asyncio.get_running_loop().time() + 2.0
    while asyncio.get_running_loop().time() < deadline:
        try:
            chunk = await asyncio.wait_for(reader.read(65535), 0.1)
        except asyncio.TimeoutError:
            chunk = b''
        if chunk:
            buffer.feed(chunk)
            frames.extend(buffer.pop_all())
        have_root_end = any(frame.frame_type == FRAME_DATA and frame.stream_id == 1 and bool(frame.flags & FLAG_END_STREAM) for frame in frames)
        have_push = any(frame.frame_type == FRAME_PUSH_PROMISE for frame in frames)
        have_pushed_end = any(frame.frame_type == FRAME_DATA and frame.stream_id == 2 and bool(frame.flags & FLAG_END_STREAM) for frame in frames)
        if have_root_end and ((not need_push) or (have_push and have_pushed_end)):
            return frames
    return frames


class HTTP2ServerPushSurfaceTests(unittest.IsolatedAsyncioTestCase):
    async def test_http2_server_push_emits_push_promise_and_promised_response(self):
        async def app(scope, receive, send):
            self.assertEqual(scope['type'], 'http')
            if scope['path'] == '/':
                self.assertIn('http.response.push', scope['extensions'])
                await send({'type': 'http.response.push', 'path': '/pushed'})
                await send({'type': 'http.response.start', 'status': 200, 'headers': [(b'content-type', b'text/plain')]})
                await send({'type': 'http.response.body', 'body': b'root'})
                return
            if scope['path'] == '/pushed':
                await send({'type': 'http.response.start', 'status': 200, 'headers': [(b'content-type', b'text/plain')]})
                await send({'type': 'http.response.body', 'body': b'pushed'})
                return
            raise AssertionError(f'unexpected path: {scope["path"]}')

        server, port = await _start_http2_server(app)
        try:
            reader, writer = await asyncio.open_connection('127.0.0.1', port)
            frame_writer = FrameWriter()
            writer.write(H2_PREFACE)
            writer.write(serialize_settings({SETTING_ENABLE_PUSH: 1}))
            writer.write(frame_writer.headers(1, _request_headers(b'/'), end_stream=True))
            await writer.drain()

            frames = await _collect_frames(reader, need_push=True)

            push_frame = next(frame for frame in frames if frame.frame_type == FRAME_PUSH_PROMISE)
            promised_stream_id, promised_block = parse_push_promise(push_frame.payload, push_frame.flags)
            self.assertEqual(promised_stream_id, 2)

            decoder = HPACKDecoder()
            decoded_push_request = decoder.decode_header_block(promised_block)
            self.assertIn((b':path', b'/pushed'), decoded_push_request)
            self.assertIn((b':method', b'GET'), decoded_push_request)

            root_headers = None
            pushed_headers = None
            root_body = bytearray()
            pushed_body = bytearray()
            for frame in frames:
                if frame.frame_type == FRAME_HEADERS and frame.stream_id == 1:
                    root_headers = decoder.decode_header_block(frame.payload)
                elif frame.frame_type == FRAME_HEADERS and frame.stream_id == promised_stream_id:
                    pushed_headers = decoder.decode_header_block(frame.payload)
                elif frame.frame_type == FRAME_DATA and frame.stream_id == 1:
                    root_body.extend(frame.payload)
                elif frame.frame_type == FRAME_DATA and frame.stream_id == promised_stream_id:
                    pushed_body.extend(frame.payload)

            self.assertIsNotNone(root_headers)
            self.assertIsNotNone(pushed_headers)
            self.assertIn((b':status', b'200'), root_headers)
            self.assertIn((b':status', b'200'), pushed_headers)
            self.assertEqual(bytes(root_body), b'root')
            self.assertEqual(bytes(pushed_body), b'pushed')

            writer.close()
            await writer.wait_closed()
        finally:
            await server.close()

    async def test_http2_server_push_is_not_advertised_when_client_disables_push(self):
        async def app(scope, receive, send):
            self.assertEqual(scope['type'], 'http')
            self.assertNotIn('http.response.push', scope['extensions'])
            await send({'type': 'http.response.start', 'status': 200, 'headers': [(b'content-type', b'text/plain')]})
            await send({'type': 'http.response.body', 'body': b'root'})

        server, port = await _start_http2_server(app)
        try:
            reader, writer = await asyncio.open_connection('127.0.0.1', port)
            frame_writer = FrameWriter()
            writer.write(H2_PREFACE)
            writer.write(serialize_settings({SETTING_ENABLE_PUSH: 0}))
            writer.write(frame_writer.headers(1, _request_headers(b'/'), end_stream=True))
            await writer.drain()

            frames = await _collect_frames(reader, need_push=False)
            self.assertFalse(any(frame.frame_type == FRAME_PUSH_PROMISE for frame in frames))
            self.assertTrue(any(frame.frame_type == FRAME_DATA and frame.stream_id == 1 for frame in frames))

            writer.close()
            await writer.wait_closed()
        finally:
            await server.close()
