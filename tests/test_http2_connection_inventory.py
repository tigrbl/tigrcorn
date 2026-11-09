from __future__ import annotations

import asyncio

from tigrcorn.config.defaults import default_config
from tigrcorn.config.load import build_config
from tigrcorn.constants import H2_PREFACE
from tigrcorn.observability.logging import AccessLogger, configure_logging
from tigrcorn.protocols.http2.codec import (
    FRAME_DATA,
    FRAME_HEADERS,
    FRAME_SETTINGS,
    FRAME_RST_STREAM,
    FrameBuffer,
    FrameWriter,
    HTTP2Frame,
    serialize_settings,
)
from tigrcorn.protocols.http2.handler import HTTP2ConnectionHandler
from tigrcorn.protocols.http2.hpack import encode_header_block
from tigrcorn.protocols.http2.state import H2StreamState
from tigrcorn.server.runner import TigrCornServer
from tigrcorn.sessions import RuntimeConnectionInventory


class _DummyReader:
    async def readexactly(self, _size: int) -> bytes:
        raise EOFError


class _DummyWriter:
    def write(self, _data: bytes) -> None:
        return None

    async def drain(self) -> None:
        return None

    def is_closing(self) -> bool:
        return False


def _handler(inventory: RuntimeConnectionInventory) -> HTTP2ConnectionHandler:
    async def app(scope, receive, send):
        return None

    inventory.open_connection(
        "conn:test:1",
        transport="tcp",
        protocols=("http2",),
        listener_id="listener:0",
        peer_id="peer:addr:127.0.0.1:12345",
        remote_address="127.0.0.1:12345",
        local_address="127.0.0.1:8443",
    )
    return HTTP2ConnectionHandler(
        app=app,
        config=default_config(),
        access_logger=AccessLogger(configure_logging("warning"), enabled=False),
        reader=_DummyReader(),
        writer=_DummyWriter(),
        client=("127.0.0.1", 12345),
        server=("127.0.0.1", 8443),
        scheme="http",
        connection_id="conn:test:1",
        connection_inventory=inventory,
    )


def _headers(path: bytes) -> bytes:
    return encode_header_block(
        [
            (b":method", b"GET"),
            (b":path", path),
            (b":scheme", b"http"),
            (b":authority", b"example"),
        ]
    )


async def _start_server(app):
    config = build_config(host="127.0.0.1", port=0, lifespan="off", http_versions=["2"])
    server = TigrCornServer(app, config)
    await server.start()
    port = server._listeners[0].server.sockets[0].getsockname()[1]
    return server, port


async def _read_response_ends(reader: asyncio.StreamReader, expected_streams: set[int]) -> None:
    buf = FrameBuffer()
    ended: set[int] = set()
    while ended != expected_streams:
        data = await asyncio.wait_for(reader.read(65535), timeout=2.0)
        assert data
        buf.feed(data)
        for frame in buf.pop_all():
            if frame.frame_type in {FRAME_HEADERS, FRAME_DATA} and frame.flags & 0x1:
                ended.add(frame.stream_id)


def test_http2_inventory_helper_opens_and_closes_session_records() -> None:
    inventory = RuntimeConnectionInventory()
    handler = _handler(inventory)

    handler._open_inventory_session(1, kind="http-request", metadata={"path": "/one"})
    handler._update_inventory_session(1, state="draining")
    handler._close_inventory_session(1, reason="done")
    handler._close_inventory_session(1, reason="done-again")

    snapshot = inventory.snapshot()
    session = snapshot["sessions"]["h2:conn:test:1:1"]
    assert session["kind"] == "http-request"
    assert session["state"] == "closed"
    assert session["stream_ids"] == ["1"]
    assert session["metadata"]["protocol"] == "http2"
    assert snapshot["connections"]["conn:test:1"]["counters"]["requests"] == 1


def test_http2_rst_stream_closes_inventory_session_idempotently() -> None:
    asyncio.run(_assert_http2_rst_stream_closes_inventory_session_idempotently())


async def _assert_http2_rst_stream_closes_inventory_session_idempotently() -> None:
    inventory = RuntimeConnectionInventory()
    handler = _handler(inventory)
    handler.state.remote_settings_seen = True
    state = H2StreamState(1)
    state.open_remote(end_stream=False)
    handler.streams.streams[1] = state
    handler._open_inventory_session(1, kind="http-request", metadata={"path": "/reset"})

    await handler._handle_frame(HTTP2Frame(frame_type=FRAME_RST_STREAM, flags=0, stream_id=1, payload=(0).to_bytes(4, "big")))
    handler._close_inventory_session(1, reason="rst-stream-again")

    session = inventory.snapshot()["sessions"]["h2:conn:test:1:1"]
    assert session["state"] == "closed"
    assert session["close_reason"] == "rst-stream-again"


def test_http2_concurrent_request_streams_share_parent_connection_inventory() -> None:
    asyncio.run(_assert_http2_concurrent_request_streams_share_parent_connection_inventory())


async def _assert_http2_concurrent_request_streams_share_parent_connection_inventory() -> None:
    seen_paths: list[str] = []
    gate = asyncio.Event()
    both_seen = asyncio.Event()

    async def app(scope, receive, send):
        seen_paths.append(scope["path"])
        if len(seen_paths) == 2:
            both_seen.set()
        await gate.wait()
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b"", "more_body": False})

    server, port = await _start_server(app)
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        frame_writer = FrameWriter()
        writer.write(H2_PREFACE)
        writer.write(serialize_settings({}))
        writer.write(frame_writer.headers(1, _headers(b"/one"), end_stream=True))
        writer.write(frame_writer.headers(3, _headers(b"/two"), end_stream=True))
        await writer.drain()

        await asyncio.wait_for(both_seen.wait(), timeout=2.0)
        inventory = server.describe()["connection_inventory"]
        connection = next(iter(inventory["connections"].values()))
        assert connection["state"] == "open"
        assert connection["session_ids"] == ["h2:conn:listener:0:1:1", "h2:conn:listener:0:1:3"]
        sessions = inventory["sessions"]
        assert {session["metadata"]["path"] for session in sessions.values()} == {"/one", "/two"}
        assert {session["kind"] for session in sessions.values()} == {"http-request"}

        gate.set()
        await _read_response_ends(reader, {1, 3})
        writer.close()
        await writer.wait_closed()
    finally:
        await server.close()


def test_http2_inventory_session_kinds_share_parent_connection() -> None:
    inventory = RuntimeConnectionInventory()
    handler = _handler(inventory)

    handler._open_inventory_session(1, kind="websocket", metadata={"path": "/ws"})
    handler._open_inventory_session(3, kind="connect-tunnel", metadata={"authority": "example:443"})

    snapshot = inventory.snapshot()
    connection = snapshot["connections"]["conn:test:1"]
    assert connection["session_ids"] == ["h2:conn:test:1:1", "h2:conn:test:1:3"]
    assert snapshot["sessions"]["h2:conn:test:1:1"]["kind"] == "websocket"
    assert snapshot["sessions"]["h2:conn:test:1:3"]["kind"] == "connect-tunnel"
    assert connection["counters"]["websockets"] == 1
    assert connection["counters"]["connect_tunnels"] == 1
