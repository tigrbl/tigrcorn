from __future__ import annotations

import pytest

from tigrcorn_protocols.client_session_coverage import (
    CLIENT_TOPOLOGY_VALUES,
    DISPOSITION_VALUES,
    GOVERNED_IDENTIFIER_FIELDS,
    INTERNAL_ONLY_FIELDS,
    PROTOCOL_CARRIER_VALUES,
    SESSION_SCOPE_VALUES,
    ClientTopology,
    CoverageDisposition,
    ProtocolCarrier,
    SessionScope,
    build_matrix_row,
    classify_default_session_scope,
    validate_governed_identifiers,
    validate_matrix_row,
)


def test_client_session_contract_vocabularies_are_stable() -> None:
    assert PROTOCOL_CARRIER_VALUES == {
        "http1",
        "http2",
        "http3_quic",
        "websocket_h1",
        "websocket_h2",
        "websocket_h3",
        "webtransport_h3_quic",
    }
    assert CLIENT_TOPOLOGY_VALUES == {
        "single_client",
        "sequential_clients",
        "bounded_interleaved_clients",
        "concurrent_clients",
        "churn_clients",
    }
    assert SESSION_SCOPE_VALUES == {
        "request_scoped",
        "tcp_connection_scoped",
        "h2_connection_scoped",
        "h2_stream_scoped",
        "quic_connection_scoped",
        "h3_stream_scoped",
        "websocket_connection_scoped",
        "webtransport_session_scoped",
        "webtransport_stream_scoped",
        "webtransport_datagram_scoped",
    }
    assert DISPOSITION_VALUES == {
        "covered",
        "required",
        "planned",
        "not_applicable",
        "fail_closed",
    }


@pytest.mark.parametrize(
    ("carrier", "scope"),
    [
        (ProtocolCarrier.HTTP1, SessionScope.REQUEST_SCOPED),
        (ProtocolCarrier.HTTP2, SessionScope.H2_STREAM_SCOPED),
        (ProtocolCarrier.HTTP3_QUIC, SessionScope.H3_STREAM_SCOPED),
        (ProtocolCarrier.WEBSOCKET_H1, SessionScope.WEBSOCKET_CONNECTION_SCOPED),
        (ProtocolCarrier.WEBSOCKET_H2, SessionScope.WEBSOCKET_CONNECTION_SCOPED),
        (ProtocolCarrier.WEBSOCKET_H3, SessionScope.WEBSOCKET_CONNECTION_SCOPED),
        (ProtocolCarrier.WEBTRANSPORT_H3_QUIC, SessionScope.WEBTRANSPORT_SESSION_SCOPED),
    ],
)
def test_default_session_scope_by_protocol_carrier(
    carrier: ProtocolCarrier,
    scope: SessionScope,
) -> None:
    assert classify_default_session_scope(carrier) is scope


def test_matrix_rows_allow_governed_identifiers() -> None:
    row = build_matrix_row(
        protocol_carrier=ProtocolCarrier.WEBTRANSPORT_H3_QUIC,
        client_topology=ClientTopology.SINGLE_CLIENT,
        disposition=CoverageDisposition.COVERED,
        lifecycle_behavior=CoverageDisposition.COVERED,
        identity_isolation=CoverageDisposition.COVERED,
        ordering_behavior=CoverageDisposition.COVERED,
        client_id="client-a",
        connection_id="conn-a",
        session_id="session-a",
        stream_id=1,
        datagram_id=2,
    )
    validate_matrix_row(row)
    assert {"client_id", "connection_id", "session_id", "stream_id", "datagram_id"} <= GOVERNED_IDENTIFIER_FIELDS


def test_matrix_rows_reject_public_lane_field() -> None:
    assert "lane" in INTERNAL_ONLY_FIELDS
    with pytest.raises(ValueError, match="lane"):
        validate_governed_identifiers({"client_id": "client-a", "lane": "bidi_stream"})


def test_matrix_rows_require_all_axes() -> None:
    with pytest.raises(ValueError, match="missing axes"):
        validate_matrix_row(
            {
                "protocol_carrier": "http1",
                "client_topology": "single_client",
                "session_scope": "request_scoped",
                "disposition": "covered",
            }
        )
