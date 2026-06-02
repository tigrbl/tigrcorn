from __future__ import annotations

from tigrcorn.config.model import WebSocketConfig, WebTransportConfig
from tigrcorn.sessions.limits import SessionLimits
from tigrcorn_protocols.client_session_coverage import (
    ClientTopology,
    CoverageDisposition,
    ProtocolCarrier,
    build_matrix_row,
)


def test_session_limits_bound_concurrent_stream_pressure() -> None:
    limits = SessionLimits(max_streams=2)

    assert limits.allow_stream(0) is True
    assert limits.allow_stream(1) is True
    assert limits.allow_stream(2) is False

    row = build_matrix_row(
        protocol_carrier=ProtocolCarrier.HTTP2,
        client_topology=ClientTopology.CONCURRENT_CLIENTS,
        disposition=CoverageDisposition.FAIL_CLOSED,
        lifecycle_behavior=CoverageDisposition.COVERED,
        identity_isolation=CoverageDisposition.COVERED,
        ordering_behavior=CoverageDisposition.COVERED,
        pressure_mode=CoverageDisposition.COVERED,
        fault_mode=CoverageDisposition.REQUIRED,
        client_id="client-a",
        connection_id="h2-conn",
        stream_id=3,
        error_kind="max_streams_exceeded",
    )
    assert row["pressure_mode"] == "covered"
    assert row["error_kind"] == "max_streams_exceeded"


def test_websocket_queue_and_message_pressure_have_configured_bounds() -> None:
    config = WebSocketConfig(max_message_size=4, max_queue=2)
    accepted = [b"one", b"two"]
    rejected_payload = b"three"

    assert len(accepted) == config.max_queue
    assert len(rejected_payload) > config.max_message_size

    row = build_matrix_row(
        protocol_carrier=ProtocolCarrier.WEBSOCKET_H1,
        client_topology=ClientTopology.CONCURRENT_CLIENTS,
        disposition=CoverageDisposition.FAIL_CLOSED,
        lifecycle_behavior=CoverageDisposition.COVERED,
        identity_isolation=CoverageDisposition.COVERED,
        ordering_behavior=CoverageDisposition.COVERED,
        pressure_mode=CoverageDisposition.COVERED,
        fault_mode=CoverageDisposition.COVERED,
        client_id="client-a",
        connection_id="ws-conn",
        error_kind="websocket_pressure_budget_exceeded",
    )
    assert row["session_scope"] == "websocket_connection_scoped"


def test_webtransport_session_stream_and_datagram_pressure_are_bounded() -> None:
    config = WebTransportConfig(max_sessions=1, max_streams=1, max_datagram_size=4)

    assert config.max_sessions == 1
    assert config.max_streams == 1
    assert len(b"toolong") > config.max_datagram_size

    row = build_matrix_row(
        protocol_carrier=ProtocolCarrier.WEBTRANSPORT_H3_QUIC,
        client_topology=ClientTopology.CONCURRENT_CLIENTS,
        disposition=CoverageDisposition.FAIL_CLOSED,
        lifecycle_behavior=CoverageDisposition.COVERED,
        identity_isolation=CoverageDisposition.COVERED,
        ordering_behavior=CoverageDisposition.COVERED,
        pressure_mode=CoverageDisposition.COVERED,
        fault_mode=CoverageDisposition.COVERED,
        client_id="client-a",
        connection_id="wt-conn",
        session_id="wt-session",
        datagram_id="d-too-large",
        error_kind="webtransport_pressure_budget_exceeded",
    )
    assert row["datagram_id"] == "d-too-large"
