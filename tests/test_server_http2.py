import asyncio
import unittest

from tigrcorn.config.load import build_config
from tigrcorn.constants import H2_PREFACE
from tigrcorn.protocols.http2.codec import (
    FLAG_END_HEADERS,
    FLAG_END_STREAM,
    FRAME_DATA,
    FRAME_HEADERS,
    FRAME_RST_STREAM,
    FRAME_SETTINGS,
    FRAME_WINDOW_UPDATE,
    FrameBuffer,
    FrameWriter,
    H2_CANCEL,
    H2_NO_ERROR,
    decode_settings,
    serialize_frame,
    serialize_settings,
)
from tigrcorn.protocols.http2.hpack import HPACKDecoder, decode_header_block, encode_header_block
from tigrcorn.server.runner import TigrCornServer


async def _start_server(app, *, max_body_size=None):
    config = build_config(
        host="127.0.0.1", port=0, lifespan="off", http_versions=["2"],
        max_body_size=max_body_size,
    )
    server = TigrCornServer(app, config)
    await server.start()
    listener = server._listeners[0]
    port = listener.server.sockets[0].getsockname()[1]
    return server, port


class HTTP2ServerTests(unittest.IsolatedAsyncioTestCase):
    async def test_http2_oversized_body_preserves_other_streams(self):
        first_chunk_received = asyncio.Event()

        async def app(scope, receive, send):
            if scope["path"] == "/streaming":
                self.assertEqual((await receive())["body"], b"abc")
                first_chunk_received.set()
                await receive()
                self.fail("an oversized chunk reached the application")
            elif scope["path"] == "/early-response":
                await send({"type": "http.response.start", "status": 200, "headers": []})
                await receive()
                self.fail("an oversized chunk reached the application")
            else:
                self.assertEqual(scope["path"], "/sibling")
                self.assertEqual((await receive())["body"], b"abcde")
                await send({"type": "http.response.start", "status": 204, "headers": []})
                await send({"type": "http.response.body", "body": b""})

        server, port = await _start_server(app, max_body_size=5)
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            try:
                frame_writer = FrameWriter()
                buffer = FrameBuffer()
                decoder = HPACKDecoder()
                statuses = {}
                resets = {}

                def headers(stream_id, path, fields=()):
                    block = encode_header_block([
                        (b":method", b"POST"), (b":path", path), (b":scheme", b"http"),
                        (b":authority", b"example"), *fields,
                    ])
                    return frame_writer.headers(stream_id, block, end_stream=False)

                async def read_until(done):
                    while not done():
                        data = await asyncio.wait_for(reader.read(65535), 2)
                        self.assertTrue(data)
                        buffer.feed(data)
                        for frame in buffer.pop_all():
                            if frame.frame_type == FRAME_HEADERS:
                                self.assertNotIn(frame.stream_id, statuses)
                                statuses[frame.stream_id] = (
                                    dict(decoder.decode_header_block(frame.payload))[b":status"],
                                    bool(frame.flags & FLAG_END_STREAM),
                                )
                            elif frame.frame_type == FRAME_RST_STREAM:
                                self.assertIn(frame.stream_id, statuses)
                                resets[frame.stream_id] = int.from_bytes(frame.payload, "big")

                writer.write(H2_PREFACE + serialize_settings({}))
                writer.write(headers(1, b"/streaming"))
                writer.write(headers(3, b"/sibling"))
                writer.write(headers(5, b"/declared", [(b"content-length", b"6")]))
                writer.write(frame_writer.data(1, b"abc", end_stream=False))
                await writer.drain()
                await asyncio.wait_for(first_chunk_received.wait(), 2)
                writer.write(frame_writer.data(1, b"def", end_stream=False))
                await writer.drain()
                await read_until(lambda: {1, 5} <= resets.keys())
                self.assertEqual(statuses, {5: (b"413", True), 1: (b"413", True)})
                self.assertEqual(resets, {5: H2_NO_ERROR, 1: H2_NO_ERROR})

                writer.write(frame_writer.data(1, b"in flight", end_stream=True))
                writer.write(frame_writer.data(3, b"abcde", end_stream=True))
                await writer.drain()
                await read_until(lambda: 3 in statuses)
                self.assertEqual(statuses[3][0], b"204")

                writer.write(headers(7, b"/early-response"))
                await writer.drain()
                await read_until(lambda: 7 in statuses)
                self.assertEqual(statuses[7], (b"200", False))
                writer.write(frame_writer.data(7, b"abcdef", end_stream=False))
                await writer.drain()
                await read_until(lambda: 7 in resets)
                self.assertEqual(resets[7], H2_CANCEL)
            finally:
                writer.close()
                await writer.wait_closed()
        finally:
            await server.close()

    async def test_http2_prior_knowledge_roundtrip(self):
        async def app(scope, receive, send):
            self.assertEqual(scope["type"], "http")
            self.assertEqual(scope["http_version"], "2")
            event = await receive()
            await send({"type": "http.response.start", "status": 200, "headers": [(b"content-type", b"text/plain")]})
            await send({"type": "http.response.body", "body": event["body"], "more_body": False})

        server, port = await _start_server(app)
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            writer.write(H2_PREFACE)
            writer.write(serialize_settings({}))
            request_headers = encode_header_block([
                (b":method", b"POST"),
                (b":path", b"/h2"),
                (b":scheme", b"http"),
                (b":authority", b"example"),
                (b"content-length", b"5"),
            ])
            frame_writer = FrameWriter()
            writer.write(frame_writer.headers(1, request_headers, end_stream=False))
            writer.write(frame_writer.data(1, b"hello", end_stream=True))
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
                        if frame.flags & FLAG_END_STREAM:
                            ended = True
                    elif frame.frame_type == FRAME_DATA:
                        body.extend(frame.payload)
                        writer.write(serialize_frame(FRAME_WINDOW_UPDATE, 0, 0, len(frame.payload).to_bytes(4, "big")))
                        writer.write(serialize_frame(FRAME_WINDOW_UPDATE, 0, frame.stream_id, len(frame.payload).to_bytes(4, "big")))
                        await writer.drain()
                        if frame.flags & FLAG_END_STREAM:
                            ended = True
            self.assertTrue(saw_settings)
            self.assertIn((b":status", b"200"), response_headers)
            self.assertEqual(bytes(body), b"hello")
            writer.close()
            await writer.wait_closed()
        finally:
            await server.close()


if __name__ == "__main__":
    unittest.main()
