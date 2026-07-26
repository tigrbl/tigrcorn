from __future__ import annotations

import asyncio
from types import SimpleNamespace

from tigrcorn_protocols.http3.handler.webtransport import (
    _HTTP3WebTransportSession,
)


class _LocalCid(bytes):
    def hex(self) -> str:
        return "localcid"


def test_child_stream_fin_does_not_disconnect_webtransport_session() -> None:
    asyncio.run(_exercise_child_stream_fin())


async def _exercise_child_stream_fin() -> None:
    handler = SimpleNamespace(
        config=SimpleNamespace(webtransport=SimpleNamespace(max_streams=4))
    )
    session = SimpleNamespace(
        runtime_id="session-1",
        quic=SimpleNamespace(local_cid=_LocalCid(b"localcid")),
    )
    transport = _HTTP3WebTransportSession(
        handler=handler,
        session=session,
        stream_id=0,
        request=SimpleNamespace(),
        client=("127.0.0.1", 10001),
        server=("127.0.0.1", 443),
        scheme="https",
        endpoint=SimpleNamespace(),
    )

    await transport.feed_stream_data(
        b"rpc", end_stream=True, stream_id=4, stream_direction="bidi"
    )

    assert transport.closed is False
    assert await transport.receive() == {
        "type": "webtransport.stream.receive",
        "session_id": transport.session_id,
        "stream_id": "4",
        "stream_direction": "bidi",
        "data": b"rpc",
        "more": False,
    }


def test_transport_abort_delivers_disconnect_before_cancelling_app() -> None:
    asyncio.run(_exercise_transport_abort())


async def _exercise_transport_abort() -> None:
    disconnect_received = asyncio.Event()

    async def app(scope, receive, send) -> None:
        message = await receive()
        assert message["type"] == "webtransport.disconnect"
        assert message["reason"] == "transport-closed"
        disconnect_received.set()

    handler = SimpleNamespace(
        app=app,
        config=SimpleNamespace(webtransport=SimpleNamespace(max_streams=4)),
        _trace_session_fields=lambda session: {},
    )
    session = SimpleNamespace(
        runtime_id="session-1",
        quic=SimpleNamespace(local_cid=_LocalCid(b"localcid")),
    )
    transport = _HTTP3WebTransportSession(
        handler=handler,
        session=session,
        stream_id=0,
        request=SimpleNamespace(),
        client=("127.0.0.1", 10001),
        server=("127.0.0.1", 443),
        scheme="https",
        endpoint=SimpleNamespace(),
    )
    transport.task = asyncio.create_task(app({}, transport.receive, None))

    await transport.abort()

    assert disconnect_received.is_set()
    assert transport.closed is True
