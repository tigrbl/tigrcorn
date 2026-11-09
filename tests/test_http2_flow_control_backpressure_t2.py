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
            (b":path", b"/flow-t2"),
            (b":scheme", b"http"),
            (b":authority", b"example"),
        ]
    )


def _window_updates(raw_writes: list[bytes]):
    frames = FrameBuffer()
    for raw in raw_writes:
        frames.feed(raw)
    return [frame for frame in frames.pop_all() if frame.frame_type == FRAME_WINDOW_UPDATE]


def test_http2_multiple_body_consumptions_replenish_flow_credit_incrementally():
    async def scenario() -> None:
        consume_tokens: asyncio.Queue[object] = asyncio.Queue()
        consumed = 0

        async def app(scope, receive, send):
            nonlocal consumed
            await consume_tokens.get()
            first = await receive()
            assert first["body"] == b"a" * 33_000
            consumed += 1
            await consume_tokens.get()
            second = await receive()
            assert second["body"] == b"b" * 33_000
            consumed += 1
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
        assert _window_updates(handler.writer.writes) == []

        await consume_tokens.put(object())
        while consumed < 1:
            await asyncio.sleep(0.01)
        first_update_count = len(_window_updates(handler.writer.writes))
        assert first_update_count == 2

        await handler._handle_data(HTTP2Frame(frame_type=FRAME_DATA, flags=0, stream_id=1, payload=b"b" * 33_000))
        await asyncio.sleep(0.02)
        assert len(_window_updates(handler.writer.writes)) == first_update_count

        await consume_tokens.put(object())
        while consumed < 2:
            await asyncio.sleep(0.01)
        assert len(_window_updates(handler.writer.writes)) == 4

    asyncio.run(scenario())
