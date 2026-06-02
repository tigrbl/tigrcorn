from __future__ import annotations

from tigrcorn.config.model import WebSocketConfig, WebTransportConfig
from tigrcorn.sessions.limits import SessionLimits
from tigrcorn_protocols.client_session_coverage import (
    ClientSessionRobustnessHarness,
    ClientTopology,
    ProtocolCarrier,
)


def test_session_limits_bound_concurrent_stream_pressure() -> None:
    limits = SessionLimits(max_streams=2)
    harness = ClientSessionRobustnessHarness(ProtocolCarrier.HTTP2, max_streams=2)
    topology = ClientTopology.CONCURRENT_CLIENTS
    harness.open("client-a", "h2-conn", "h2-session")

    assert limits.allow_stream(0) is True
    assert limits.allow_stream(1) is True
    assert limits.allow_stream(2) is False

    harness.send("client-a", "h2-conn", "h2-session", topology, "one", stream_id=0)
    harness.send("client-a", "h2-conn", "h2-session", topology, "two", stream_id=1)
    try:
        harness.send("client-a", "h2-conn", "h2-session", topology, "three", stream_id=2)
    except BufferError as exc:
        assert "stream pressure" in str(exc)
    else:  # pragma: no cover - defensive guard for the T2 contract
        raise AssertionError("stream pressure was not bounded")

    assert harness.errors[-1]["pressure_mode"] == "covered"
    assert harness.errors[-1]["error_kind"] == "max_streams_exceeded"
    assert harness.errors[-1]["stream_id"] == 2


def test_websocket_queue_and_message_pressure_have_configured_bounds() -> None:
    config = WebSocketConfig(max_message_size=4, max_queue=2)
    harness = ClientSessionRobustnessHarness(
        ProtocolCarrier.WEBSOCKET_H1,
        max_message_size=config.max_message_size,
        max_queue=config.max_queue,
    )
    topology = ClientTopology.CONCURRENT_CLIENTS
    harness.open("client-a", "ws-conn", "ws-session")
    harness.send("client-a", "ws-conn", "ws-session", topology, b"one")
    harness.send("client-a", "ws-conn", "ws-session", topology, b"two")

    try:
        harness.send("client-a", "ws-conn", "ws-session", topology, b"three")
    except BufferError as exc:
        assert "message pressure" in str(exc)
    else:  # pragma: no cover - defensive guard for the T2 contract
        raise AssertionError("websocket message pressure was not bounded")

    assert harness.errors[-1]["session_scope"] == "websocket_connection_scoped"
    assert harness.errors[-1]["error_kind"] == "message_pressure_budget_exceeded"


def test_webtransport_session_stream_and_datagram_pressure_are_bounded() -> None:
    config = WebTransportConfig(max_sessions=1, max_streams=1, max_datagram_size=4)
    harness = ClientSessionRobustnessHarness(
        ProtocolCarrier.WEBTRANSPORT_H3_QUIC,
        max_sessions=config.max_sessions,
        max_streams=config.max_streams,
        max_datagram_size=config.max_datagram_size,
    )
    topology = ClientTopology.CONCURRENT_CLIENTS
    harness.open("client-a", "wt-conn", "wt-session")

    assert config.max_sessions == 1
    assert config.max_streams == 1
    harness.send("client-a", "wt-conn", "wt-session", topology, b"ok", stream_id="stream-1")

    try:
        harness.send(
            "client-a",
            "wt-conn",
            "wt-session",
            topology,
            b"toolong",
            datagram_id="d-too-large",
        )
    except BufferError as exc:
        assert "datagram pressure" in str(exc)
    else:  # pragma: no cover - defensive guard for the T2 contract
        raise AssertionError("webtransport datagram pressure was not bounded")

    assert harness.errors[-1]["datagram_id"] == "d-too-large"
    assert harness.errors[-1]["error_kind"] == "datagram_pressure_budget_exceeded"
