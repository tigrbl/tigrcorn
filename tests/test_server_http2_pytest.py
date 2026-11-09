import asyncio

import pytest

from tigrcorn.config.load import build_config
from tigrcorn.constants import H2_PREFACE
from tigrcorn.protocols.http2.codec import (
    FLAG_END_HEADERS,
    FLAG_END_STREAM,
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


async def _start_server(app):
    config = build_config(host="127.0.0.1", port=0, lifespan="off", http_versions=["2"])
    server = TigrCornServer(app, config)
    await server.start()
    listener = server._listeners[0]
    port = listener.server.sockets[0].getsockname()[1]
    return server, port


@pytest.mark.asyncio
async def test_http2_prior_knowledge_roundtrip():
    async def app(scope, receive, send):
        assert scope["type"] == "http"
        assert scope["http_version"] == "2"
        event = await receive()
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"text/plain")],
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": event["body"],
                "more_body": False,
            }
        )

    server, port = await _start_server(app)
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write(H2_PREFACE)
        writer.write(serialize_settings({}))
        request_headers = encode_header_block(
            [
                (b":method", b"POST"),
                (b":path", b"/h2"),
                (b":scheme", b"http"),
                (b":authority", b"example"),
                (b"content-length", b"5"),
            ]
        )
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
            assert data
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
                    writer.write(
                        serialize_frame(
                            FRAME_WINDOW_UPDATE,
                            0,
                            0,
                            len(frame.payload).to_bytes(4, "big"),
                        )
                    )
                    writer.write(
                        serialize_frame(
                            FRAME_WINDOW_UPDATE,
                            0,
                            frame.stream_id,
                            len(frame.payload).to_bytes(4, "big"),
                        )
                    )
                    await writer.drain()
                    if frame.flags & FLAG_END_STREAM:
                        ended = True
        assert saw_settings
        assert (b":status", b"200") in response_headers
        assert bytes(body) == b"hello"
        writer.close()
        await writer.wait_closed()
    finally:
        await server.close()
