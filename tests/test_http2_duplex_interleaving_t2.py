from __future__ import annotations

import asyncio

from tigrcorn.config.defaults import default_config
from tigrcorn.observability.logging import AccessLogger, configure_logging
from tigrcorn.protocols.http2.codec import FLAG_END_HEADERS, FLAG_END_STREAM, FRAME_DATA, FRAME_HEADERS, FrameBuffer, HTTP2Frame
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
            (b":path", b"/duplex-t2"),
            (b":scheme", b"http"),
            (b":authority", b"example"),
        ]
    )


def _data_frames(raw_writes: list[bytes]):
    frames = FrameBuffer()
    for raw in raw_writes:
        frames.feed(raw)
    return [frame for frame in frames.pop_all() if frame.frame_type == FRAME_DATA]


def test_http2_app_failure_after_partial_live_response_closes_local_stream_side():
    async def scenario() -> None:
        response_started = asyncio.Event()

        async def app(scope, receive, send):
            event = await receive()
            assert event["body"] == b"first"
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"partial", "more_body": True})
            response_started.set()
            raise RuntimeError("boom after partial response")

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
        await asyncio.wait_for(response_started.wait(), timeout=1)
        await asyncio.sleep(0.05)

        data_frames = _data_frames(handler.writer.writes)
        assert any(frame.payload == b"partial" and not (frame.flags & FLAG_END_STREAM) for frame in data_frames)
        assert any(frame.payload == b"" and frame.flags & FLAG_END_STREAM for frame in data_frames)
        state = handler.streams.find(1)
        assert state is not None
        assert state.local_closed is True
        assert state.end_stream_received is False

    asyncio.run(scenario())
