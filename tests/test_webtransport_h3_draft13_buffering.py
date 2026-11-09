from __future__ import annotations

import pytest

from tigrcorn.webtransport.wire import WebTransportWireError, WebTransportWireRuntime


def test_webtransport_h3_draft13_buffered_stream_before_connect() -> None:
    runtime = WebTransportWireRuntime(max_sessions=1, buffer_limit=2)

    runtime.buffer_before_session("4", "stream", b"payload")

    assert runtime.flush_buffered("4")[0].payload == b"payload"


def test_webtransport_h3_draft13_buffered_stream_limit_rejected() -> None:
    runtime = WebTransportWireRuntime(max_sessions=1, buffer_limit=1)
    runtime.buffer_before_session("4", "stream", b"one")

    with pytest.raises(WebTransportWireError, match="WT_BUFFERED_STREAM_REJECTED"):
        runtime.buffer_before_session("4", "stream", b"two")


def test_webtransport_h3_draft13_orphan_datagram_dropped() -> None:
    runtime = WebTransportWireRuntime(max_sessions=1)

    with pytest.raises(WebTransportWireError, match="WT_SESSION_GONE"):
        runtime.receive_datagram("404", b"orphan")
