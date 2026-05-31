from __future__ import annotations

import asyncio

from tigrcorn.config.defaults import default_config
from tigrcorn.observability.logging import AccessLogger, configure_logging
from tigrcorn.protocols.http2.codec import FLAG_END_HEADERS, FLAG_END_STREAM, FRAME_DATA, FRAME_HEADERS, FRAME_RST_STREAM, HTTP2Frame
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
            (b":path", b"/upload"),
            (b":scheme", b"http"),
            (b":authority", b"example"),
        ]
    )


def _handler(app) -> HTTP2ConnectionHandler:
    return HTTP2ConnectionHandler(
        app=app,
        config=default_config(),
        access_logger=AccessLogger(configure_logging("warning"), enabled=False),
        reader=_DummyReader(),
        writer=_CapturingWriter(),
        client=None,
        server=None,
        scheme="http",
    )


def test_http2_end_stream_data_chunk_is_delivered_as_terminal_body_event():
    async def scenario() -> None:
        received: list[dict] = []

        async def app(scope, receive, send):
            received.append(await receive())
            await send({"type": "http.response.start", "status": 204, "headers": []})
            await send({"type": "http.response.body", "body": b"", "more_body": False})

        handler = _handler(app)
        handler.state.remote_settings_seen = True
        await handler._handle_headers(HTTP2Frame(frame_type=FRAME_HEADERS, flags=FLAG_END_HEADERS, stream_id=1, payload=_headers()))
        await asyncio.sleep(0)

        await handler._handle_data(
            HTTP2Frame(frame_type=FRAME_DATA, flags=FLAG_END_STREAM, stream_id=1, payload=b"terminal")
        )
        await asyncio.sleep(0.05)

        assert received == [{"type": "http.request", "body": b"terminal", "more_body": False}]
        assert handler.streams.is_closed(1)

    asyncio.run(scenario())


def test_http2_rst_stream_cancels_incremental_request_body_dispatch_task():
    async def scenario() -> None:
        cancelled = asyncio.Event()

        async def app(scope, receive, send):
            try:
                await receive()
                await receive()
            except asyncio.CancelledError:
                cancelled.set()
                raise

        handler = _handler(app)
        handler.state.remote_settings_seen = True
        await handler._handle_headers(HTTP2Frame(frame_type=FRAME_HEADERS, flags=FLAG_END_HEADERS, stream_id=1, payload=_headers()))
        await asyncio.sleep(0)
        await handler._handle_data(HTTP2Frame(frame_type=FRAME_DATA, flags=0, stream_id=1, payload=b"first"))
        await asyncio.sleep(0)

        await handler._handle_rst_stream(
            HTTP2Frame(frame_type=FRAME_RST_STREAM, flags=0, stream_id=1, payload=(8).to_bytes(4, "big"))
        )
        await asyncio.wait_for(cancelled.wait(), timeout=1)

        assert handler.streams.is_closed(1)
        assert 1 not in handler.stream_tasks

    asyncio.run(scenario())
