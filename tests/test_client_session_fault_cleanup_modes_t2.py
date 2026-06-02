from __future__ import annotations

import pytest

from tests.support.client_session_matrix import ClientSessionRobustnessHarness
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
    harness = ClientSessionRobustnessHarness(ProtocolCarrier.WEBTRANSPORT_H3_QUIC)
    topology = ClientTopology.CONCURRENT_CLIENTS
    harness.open("client-a", "wt-conn-a", "wt-session-a")

    with pytest.raises(PermissionError, match="cross-client"):
        harness.send("client-b", "wt-conn-a", "wt-session-a", topology, "stolen")

    assert harness.errors[-1]["fault_mode"] == "covered"
    assert harness.errors[-1]["error_kind"] == "cross_client_session_access"


def test_post_close_send_is_rejected_and_session_cleanup_is_visible() -> None:
    harness = ClientSessionRobustnessHarness(ProtocolCarrier.WEBSOCKET_H1)
    topology = ClientTopology.CHURN_CLIENTS
    harness.open("client-a", "ws-conn-a", "ws-session-a")
    harness.close("client-a", "ws-conn-a", "ws-session-a", topology)

    with pytest.raises(RuntimeError, match="post-close"):
        harness.send("client-a", "ws-conn-a", "ws-session-a", topology, "late")

    assert harness.sessions["ws-session-a"].closed is True
    assert harness.errors[-1]["error_kind"] == "post_close_send"


def test_timeout_cancel_and_unknown_session_cleanup_fail_closed() -> None:
    harness = ClientSessionRobustnessHarness(ProtocolCarrier.HTTP3_QUIC)
    topology = ClientTopology.CHURN_CLIENTS
    harness.open("client-a", "h3-conn-a", "h3-session-a")
    harness.open("client-b", "h3-conn-b", "h3-session-b")

    harness.timeout("client-a", "h3-conn-a", "h3-session-a", topology)
    harness.cancel("client-b", "h3-conn-b", "h3-session-b", topology)
    with pytest.raises(KeyError, match="unknown session"):
        harness.send("client-c", "h3-conn-c", "missing-session", topology, "late")

    assert [error["error_kind"] for error in harness.errors] == [
        "timeout",
        "cancelled",
        "unknown_session",
    ]
    assert harness.sessions["h3-session-a"].closed is True
    assert harness.sessions["h3-session-b"].closed is True


def test_malformed_payload_is_rejected_fail_closed() -> None:
    harness = ClientSessionRobustnessHarness(ProtocolCarrier.HTTP1)
    topology = ClientTopology.SINGLE_CLIENT
    harness.open("client-a", "http1-conn", "request-session")

    with pytest.raises(ValueError, match="malformed payload"):
        harness.send("client-a", "http1-conn", "request-session", topology, {})

    assert harness.errors[-1]["error_kind"] == "malformed_payload"


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
