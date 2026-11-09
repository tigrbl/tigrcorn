from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from tigrcorn_protocols.http3.handler.webtransport_streams import (
    HTTP3WebTransportStreamsMixin,
)


class _StreamsHarness(HTTP3WebTransportStreamsMixin):
    @staticmethod
    def _stream_is_client_initiated_unidi(stream_id: int) -> bool:
        return stream_id & 0x03 == 0x02

    @staticmethod
    def _webtransport_release_stream(_webtransport: object, _stream_id: int) -> None:
        return None


def _session(webtransport: object, *, stream_id: int) -> SimpleNamespace:
    return SimpleNamespace(
        webtransport_stream_owners={stream_id: 0},
        webtransport_sessions={0: webtransport},
        webtransport_streams={stream_id},
        webtransport_stream_prefaces={},
        h3=SimpleNamespace(abandon_stream=lambda _stream_id: None),
    )


def test_known_client_unidi_continuation_keeps_receive_only_direction() -> None:
    webtransport = SimpleNamespace(feed_stream_data=AsyncMock())
    session = _session(webtransport, stream_id=6)

    handled, remaining = asyncio.run(
        _StreamsHarness()._consume_webtransport_stream_event_locked(
            session,
            6,
            b"continuation",
            fin=False,
        )
    )

    assert handled is True
    assert remaining == b""
    webtransport.feed_stream_data.assert_awaited_once_with(
        b"continuation",
        end_stream=False,
        disconnect_on_end=False,
        stream_id=6,
        stream_direction="client_to_server",
    )


def test_known_client_unidi_fin_keeps_receive_only_direction() -> None:
    webtransport = SimpleNamespace(feed_stream_data=AsyncMock())
    session = _session(webtransport, stream_id=6)

    handled, remaining = asyncio.run(
        _StreamsHarness()._consume_webtransport_stream_event_locked(
            session,
            6,
            b"",
            fin=True,
        )
    )

    assert handled is True
    assert remaining == b""
    webtransport.feed_stream_data.assert_awaited_once_with(
        b"",
        end_stream=True,
        disconnect_on_end=False,
        stream_id=6,
        stream_direction="client_to_server",
    )


def test_known_bidi_continuation_remains_bidirectional() -> None:
    webtransport = SimpleNamespace(feed_stream_data=AsyncMock())
    session = _session(webtransport, stream_id=4)

    handled, remaining = asyncio.run(
        _StreamsHarness()._consume_webtransport_stream_event_locked(
            session,
            4,
            b"continuation",
            fin=False,
        )
    )

    assert handled is True
    assert remaining == b""
    webtransport.feed_stream_data.assert_awaited_once_with(
        b"continuation",
        end_stream=False,
        disconnect_on_end=False,
        stream_id=4,
        stream_direction="bidi",
    )
