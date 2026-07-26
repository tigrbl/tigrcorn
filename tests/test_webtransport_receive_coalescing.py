from __future__ import annotations

import asyncio
from types import SimpleNamespace

from tigrcorn_protocols.http3.handler.webtransport import (
    WEBTRANSPORT_ASGI_CHUNK_SIZE,
    _HTTP3WebTransportSession,
)


def _session() -> _HTTP3WebTransportSession:
    session = object.__new__(_HTTP3WebTransportSession)
    session.closed = False
    session.stream_id = 0
    session.session_id = "session-1"
    session.client_stream_buffers = {}
    session.receive = SimpleNamespace(put=None)
    session._trace_webtransport = lambda *args, **kwargs: None
    session._trace_session_fields = lambda: {}
    return session


def test_client_unidi_data_is_coalesced_without_changing_byte_order() -> None:
    async def scenario() -> None:
        session = _session()
        events: list[dict] = []

        async def put(event: dict) -> None:
            events.append(event)

        session.receive.put = put
        first = b"a" * 9_000
        second = b"b" * 9_000
        await session.feed_stream_data(
            first,
            stream_id=6,
            stream_direction="client_to_server",
        )
        assert events == []
        await session.feed_stream_data(
            second,
            stream_id=6,
            stream_direction="client_to_server",
        )
        assert len(events) == 1
        assert events[0]["data"] == (first + second)[:WEBTRANSPORT_ASGI_CHUNK_SIZE]
        assert events[0]["more"] is True
        await session.feed_stream_data(
            b"",
            end_stream=True,
            stream_id=6,
            stream_direction="client_to_server",
        )
        assert b"".join(event["data"] for event in events) == first + second
        assert events[-1]["more"] is False

    asyncio.run(scenario())
