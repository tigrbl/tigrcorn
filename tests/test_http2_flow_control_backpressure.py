from __future__ import annotations

import asyncio

from tigrcorn.config.defaults import default_config
from tigrcorn.observability.logging import AccessLogger, configure_logging
from tigrcorn.protocols.http2.codec import FLAG_END_HEADERS, FRAME_DATA, FRAME_HEADERS, FRAME_WINDOW_UPDATE, FrameBuffer, HTTP2Frame
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
            (b":path", b"/flow"),
            (b":scheme", b"http"),
            (b":authority", b"example"),
        ]
    )


def test_http2_window_update_is_driven_by_app_consumption():
    async def scenario() -> None:
        release_consume = asyncio.Event()
        consumed = asyncio.Event()

        async def app(scope, receive, send):
            await release_consume.wait()
            event = await receive()
            assert event["body"] == b"a" * 33_000
            consumed.set()
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"ok", "more_body": False})

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
        await handler._handle_data(HTTP2Frame(frame_type=FRAME_DATA, flags=0, stream_id=1, payload=b"a" * 33_000))
        await asyncio.sleep(0.02)

        before_consume = FrameBuffer()
        for raw in handler.writer.writes:
            before_consume.feed(raw)
        assert [frame for frame in before_consume.pop_all() if frame.frame_type == FRAME_WINDOW_UPDATE] == []

        release_consume.set()
        await asyncio.wait_for(consumed.wait(), timeout=1)
        await asyncio.sleep(0.02)

        after_consume = FrameBuffer()
        for raw in handler.writer.writes:
            after_consume.feed(raw)
        updates = [frame for frame in after_consume.pop_all() if frame.frame_type == FRAME_WINDOW_UPDATE]
        assert [frame.stream_id for frame in updates] == [0, 1]

    asyncio.run(scenario())
