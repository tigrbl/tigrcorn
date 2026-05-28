from __future__ import annotations

import asyncio

from tigrcorn.config.defaults import default_config
from tigrcorn.observability.logging import AccessLogger, configure_logging
from tigrcorn.protocols.http2.codec import FLAG_END_HEADERS, FRAME_DATA, FRAME_HEADERS, FrameBuffer, HTTP2Frame
from tigrcorn.protocols.http2.handler import HTTP2ConnectionHandler
from tigrcorn.protocols.http2.hpack import encode_header_block


class _DummyReader:
    async def readexactly(self, n: int) -> bytes:
        raise EOFError


class _CapturingWriter:
    def __init__(self) -> None:
        self.writes: list[bytes] = []

    def write(self, data: bytes) -> None:
        self.writes.append(data)

    async def drain(self) -> None:
        return None

    def is_closing(self) -> bool:
        return False


def _headers() -> bytes:
    return encode_header_block(
        [
            (b":method", b"POST"),
            (b":path", b"/duplex"),
            (b":scheme", b"http"),
            (b":authority", b"example"),
        ]
    )


def test_http2_response_body_can_interleave_before_request_end_stream():
    async def scenario() -> None:
        first_received = asyncio.Event()
        second_received = asyncio.Event()

        async def app(scope, receive, send):
            first = await receive()
            assert first["body"] == b"first"
            first_received.set()
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"ack:", "more_body": True})
            second = await receive()
            assert second["body"] == b"second"
            second_received.set()
            await send({"type": "http.response.body", "body": b"done", "more_body": False})

        handler = HTTP2ConnectionHandler(
            app=app,
            config=default_config(),
            access_logger=AccessLogger(configure_logging("warning"), enabled=False),
            reader=_DummyReader(),
            writer=_CapturingWriter(),
            client=None,
            server=None,
            scheme="http",
        )
        handler.state.remote_settings_seen = True
        await handler._handle_headers(HTTP2Frame(frame_type=FRAME_HEADERS, flags=FLAG_END_HEADERS, stream_id=1, payload=_headers()))
        await asyncio.sleep(0)
        await handler._handle_data(HTTP2Frame(frame_type=FRAME_DATA, flags=0, stream_id=1, payload=b"first"))
        await asyncio.wait_for(first_received.wait(), timeout=1)
        await asyncio.sleep(0.02)

        before_second_request_chunk = FrameBuffer()
        for raw in handler.writer.writes:
            before_second_request_chunk.feed(raw)
        frames = before_second_request_chunk.pop_all()
        assert any(frame.frame_type == FRAME_HEADERS for frame in frames)
        assert any(frame.frame_type == FRAME_DATA and frame.payload == b"ack:" for frame in frames)

        await handler._handle_data(HTTP2Frame(frame_type=FRAME_DATA, flags=0, stream_id=1, payload=b"second"))
        await asyncio.wait_for(second_received.wait(), timeout=1)

    asyncio.run(scenario())
