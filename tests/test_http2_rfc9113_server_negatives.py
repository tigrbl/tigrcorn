from __future__ import annotations

import asyncio
import unittest

from tigrcorn.config.load import build_config
from tigrcorn.constants import H2_PREFACE
from tigrcorn.protocols.http2.codec import FLAG_END_STREAM, FRAME_DATA, FRAME_HEADERS, FRAME_PUSH_PROMISE, FRAME_SETTINGS, FrameBuffer, FrameWriter, HTTP2Frame, serialize_settings
from tigrcorn.protocols.http2.hpack import HPACKEncoder, decode_header_block
from tigrcorn.server.runner import TigrCornServer


async def _start_server(app):
    config = build_config(host="127.0.0.1", port=0, lifespan="off", http_versions=["2"])
    server = TigrCornServer(app, config)
    await server.start()
    listener = server._listeners[0]
    port = listener.server.sockets[0].getsockname()[1]
    return server, port


def _encode_headers(headers: list[tuple[bytes, bytes]]) -> bytes:
    return HPACKEncoder().encode_header_block(headers)


async def _collect_until_close(reader: asyncio.StreamReader, *, timeout: float = 1.0) -> list[HTTP2Frame]:
    buffer = FrameBuffer()
    frames: list[HTTP2Frame] = []
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        remaining = max(0.01, deadline - loop.time())
        try:
            chunk = await asyncio.wait_for(reader.read(65535), remaining)
        except asyncio.TimeoutError:
            break
        if not chunk:
            break
        buffer.feed(chunk)
        frames.extend(buffer.pop_all())
    return frames


async def _send_request(
    port: int,
    headers: list[tuple[bytes, bytes]],
    *,
    body: bytes = b"",
    end_stream_on_headers: bool = False,
) -> list[HTTP2Frame]:
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    try:
        frame_writer = FrameWriter()
        writer.write(H2_PREFACE)
        writer.write(serialize_settings({}))
        writer.write(frame_writer.headers(1, _encode_headers(headers), end_stream=end_stream_on_headers and not body))
        if body:
            writer.write(frame_writer.data(1, body, end_stream=True))
        await writer.drain()
        return await _collect_until_close(reader)
    finally:
        writer.close()
        await writer.wait_closed()


class HTTP2RFC9113ServerNegativeTests(unittest.IsolatedAsyncioTestCase):
    async def test_http2_server_rejects_malformed_rfc9113_requests(self):
        invoked = False

        async def app(scope, receive, send):
            nonlocal invoked
            invoked = True
            await send({"type": "http.response.start", "status": 200, "headers": [(b"content-type", b"text/plain")]})
            await send({"type": "http.response.body", "body": b"ok"})

        bad_requests = [
            (
                [
                    (b":method", b"POST"),
                    (b":path", b"/upload"),
                    (b":scheme", b"http"),
                    (b":authority", b"example"),
                    (b"content-length", b"3"),
                ],
                b"hello",
                False,
            ),
            (
                [
                    (b":method", b"GET"),
                    (b":path", b"/"),
                    (b":scheme", b"http"),
                    (b":authority", b"good.example"),
                    (b"host", b"evil.example"),
                ],
                b"",
                True,
            ),
            (
                [
                    (b":method", b"GET"),
                    (b":path", b""),
                    (b":scheme", b"http"),
                    (b":authority", b"example"),
                ],
                b"",
                True,
            ),
            (
                [
                    (b":method", b"GET"),
                    (b":path", b"/"),
                    (b":scheme", b"http"),
                    (b":authority", b"example"),
                    (b"x-test", b" bad "),
                ],
                b"",
                True,
            ),
        ]

        server, port = await _start_server(app)
        try:
            for headers, body, end_stream_on_headers in bad_requests:
                frames = await _send_request(port, headers, body=body, end_stream_on_headers=end_stream_on_headers)
                response_headers = [
                    decode_header_block(frame.payload)
                    for frame in frames
                    if frame.frame_type == FRAME_HEADERS and frame.stream_id == 1
                ]
                self.assertFalse(response_headers, msg=f"unexpected response HEADERS for {headers!r}")
                self.assertTrue(any(frame.frame_type == FRAME_SETTINGS for frame in frames))
            self.assertFalse(invoked)
        finally:
            await server.close()

    async def test_http2_server_rejects_unsafe_push_methods_on_wire(self):
        async def app(scope, receive, send):
            await send({"type": "http.response.push", "path": "/pushed", "method": "POST"})
            await send({"type": "http.response.start", "status": 200, "headers": [(b"content-type", b"text/plain")]})
            await send({"type": "http.response.body", "body": b"root"})

        server, port = await _start_server(app)
        try:
            frames = await _send_request(
                port,
                [
                    (b":method", b"GET"),
                    (b":path", b"/"),
                    (b":scheme", b"http"),
                    (b":authority", b"example"),
                ],
                end_stream_on_headers=True,
            )
            self.assertFalse(any(frame.frame_type == FRAME_PUSH_PROMISE for frame in frames))
            response_headers = [
                decode_header_block(frame.payload)
                for frame in frames
                if frame.frame_type == FRAME_HEADERS and frame.stream_id == 1
            ]
            self.assertTrue(response_headers)
            self.assertIn((b":status", b"500"), response_headers[-1])
            response_body = b"".join(
                frame.payload
                for frame in frames
                if frame.frame_type == FRAME_DATA and frame.stream_id == 1
            )
            self.assertEqual(response_body, b"internal server error")
            self.assertTrue(any(frame.frame_type == FRAME_DATA and frame.stream_id == 1 and frame.flags & FLAG_END_STREAM for frame in frames))
        finally:
            await server.close()


if __name__ == "__main__":
    unittest.main()
