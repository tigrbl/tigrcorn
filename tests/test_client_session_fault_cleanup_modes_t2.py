from __future__ import annotations

import pytest

from tests.support.client_session_matrix import ClientSessionTopologyHarness
from tigrcorn_protocols.client_session_coverage import (
    ClientTopology,
    CoverageDisposition,
    ProtocolCarrier,
    build_matrix_row,
    validate_governed_identifiers,
)


def test_governed_records_reject_internal_lane_field() -> None:
    with pytest.raises(ValueError, match="lane"):
        validate_governed_identifiers(
            {
                "client_id": "client-a",
                "connection_id": "wt-conn",
                "session_id": "wt-session",
                "lane": "bidi_stream",
            }
        )


def test_cross_client_session_access_fails_closed() -> None:
    harness = ClientSessionTopologyHarness(ProtocolCarrier.WEBTRANSPORT_H3_QUIC)
    topology = ClientTopology.CONCURRENT_CLIENTS
    harness.open("client-a", "wt-conn-a", "wt-session-a", topology)

    with pytest.raises(PermissionError, match="cross-client"):
        harness.send("client-b", "wt-conn-a", "wt-session-a", topology, "stolen")

    row = build_matrix_row(
        protocol_carrier=ProtocolCarrier.WEBTRANSPORT_H3_QUIC,
        client_topology=topology,
        disposition=CoverageDisposition.FAIL_CLOSED,
        lifecycle_behavior=CoverageDisposition.COVERED,
        identity_isolation=CoverageDisposition.COVERED,
        ordering_behavior=CoverageDisposition.REQUIRED,
        pressure_mode=CoverageDisposition.REQUIRED,
        fault_mode=CoverageDisposition.COVERED,
        client_id="client-b",
        connection_id="wt-conn-a",
        session_id="wt-session-a",
        error_kind="cross_client_session_access",
    )
    assert row["fault_mode"] == "covered"


def test_post_close_send_is_rejected_and_session_cleanup_is_visible() -> None:
    harness = ClientSessionTopologyHarness(ProtocolCarrier.WEBSOCKET_H1)
    topology = ClientTopology.CHURN_CLIENTS
    harness.open("client-a", "ws-conn-a", "ws-session-a", topology)
    harness.close("client-a", "ws-conn-a", "ws-session-a", topology)

    with pytest.raises(RuntimeError, match="post-close"):
        harness.send("client-a", "ws-conn-a", "ws-session-a", topology, "late")

    assert harness.sessions["ws-session-a"].closed is True


def test_native_webtransport_message_event_is_unsupported_fault() -> None:
    event = {"type": "webtransport.message.receive", "session_id": "wt-session"}

    row = build_matrix_row(
        protocol_carrier=ProtocolCarrier.WEBTRANSPORT_H3_QUIC,
        client_topology=ClientTopology.SINGLE_CLIENT,
        disposition=CoverageDisposition.FAIL_CLOSED,
        lifecycle_behavior=CoverageDisposition.COVERED,
        identity_isolation=CoverageDisposition.COVERED,
        ordering_behavior=CoverageDisposition.REQUIRED,
        pressure_mode=CoverageDisposition.REQUIRED,
        fault_mode=CoverageDisposition.COVERED,
        client_id="client-a",
        connection_id="wt-conn",
        session_id=event["session_id"],
        error_kind="unsupported_native_webtransport_message",
    )

    assert event["type"].startswith("webtransport.message.")
    assert row["disposition"] == "fail_closed"
