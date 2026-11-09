from __future__ import annotations

import json

import pytest

from tigrcorn.observability.protocol import (
    ProtocolObservabilityError,
    certification_evidence_links,
    lifecycle_event,
    make_observability_record,
    protocol_label_schema,
    protocol_transport_labels,
    propagate_otel_context,
    quic_operational_labels,
    redact_and_bound_labels,
    redact_mapping,
    tls_alpn_labels,
    validate_label_config,
)


def test_observability_protocol_label_schema() -> None:
    schema = protocol_label_schema()

    assert schema["schema_version"] == 1
    assert [item["name"] for item in schema["labels"]] == [
        "protocol",
        "transport",
        "tls_version",
        "alpn",
        "profile",
        "listener_id",
        "lifecycle",
    ]
    assert "path" in schema["cardinality"]["hashed"]
    assert "token" in schema["redaction"]


def test_observability_deterministic_event_shape() -> None:
    first = make_observability_record(
        kind="event",
        name="http.request",
        labels={"transport": "tcp", "protocol": "http1", "profile": "default"},
        attributes={"z": 2, "a": 1},
    )
    second = make_observability_record(
        kind="event",
        name="http.request",
        labels={"profile": "default", "protocol": "http1", "transport": "tcp"},
        attributes={"a": 1, "z": 2},
    )

    assert first == second
    assert first["schema_version"] == 1
    assert tuple(first) == ("attributes", "kind", "labels", "name", "schema_version")
    assert json.dumps(first, sort_keys=True)


def test_observability_protocol_transport_labels() -> None:
    labels = protocol_transport_labels(protocol="http3", transport="quic", profile="strict-h3-edge")

    assert labels["protocol"] == "http3"
    assert labels["transport"] == "quic"
    assert labels["profile"] == "strict-h3-edge"


def test_observability_tls_alpn_labels() -> None:
    labels = tls_alpn_labels(
        protocol="http2",
        transport="tcp",
        tls_version="TLSv1.3",
        alpn="h2",
    )

    assert labels["tls_version"] == "TLSv1.3"
    assert labels["alpn"] == "h2"
    assert labels["protocol"] == "http2"


def test_observability_websocket_webtransport_lifecycle() -> None:
    websocket = lifecycle_event(
        protocol="websocket",
        transport="tcp",
        lifecycle="accepted",
        session_id="ws-session-123",
    )
    webtransport = lifecycle_event(
        protocol="webtransport",
        transport="quic",
        lifecycle="datagram_sent",
        session_id="wt-session-456",
    )

    assert websocket["name"] == "websocket.accepted"
    assert websocket["labels"]["session_id_hash"]
    assert "ws-session-123" not in json.dumps(websocket)
    assert webtransport["name"] == "webtransport.datagram_sent"
    assert webtransport["labels"]["session_id_hash"]
    assert "wt-session-456" not in json.dumps(webtransport)


def test_observability_otel_context_propagation() -> None:
    record = propagate_otel_context(
        {"traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"},
        {"protocol": "http1", "transport": "tcp"},
    )

    assert record["kind"] == "trace"
    assert record["labels"]["trace_id"] == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert record["labels"]["span_id"] == "00f067aa0ba902b7"


def test_observability_quic_rtt_loss_migration() -> None:
    record = quic_operational_labels(
        rtt_ms=12.34567,
        loss_packets=3,
        migration="validated",
        qlog_secret="secret-qlog-material",
    )
    rendered = json.dumps(record, sort_keys=True)

    assert record["labels"]["quic_rtt_ms"] == 12.346
    assert record["labels"]["quic_loss_packets"] == 3
    assert record["labels"]["quic_migration"] == "validated"
    assert record["attributes"]["qlog_secret"] == "[redacted]"
    assert "secret-qlog-material" not in rendered


def test_observability_redaction() -> None:
    redacted = redact_mapping(
        {
            "authorization": "Bearer secret",
            "client_certificate": "cert-material",
            "nested": {"token": "abc"},
            "safe": "value",
        }
    )

    assert redacted == {
        "authorization": "[redacted]",
        "client_certificate": "[redacted]",
        "nested": {"token": "[redacted]"},
        "safe": "value",
    }


def test_observability_cardinality_bounds() -> None:
    labels = redact_and_bound_labels(
        {
            "protocol": "http1",
            "transport": "tcp",
            "path": "/accounts/123456/private",
            "peer_id": "peer-123456",
        }
    )
    rendered = json.dumps(labels, sort_keys=True)

    assert labels["path_hash"]
    assert labels["peer_id_hash"]
    assert "/accounts/123456/private" not in rendered
    assert "peer-123456" not in rendered


def test_observability_fail_closed_on_unsafe_label_config() -> None:
    with pytest.raises(ProtocolObservabilityError, match="unsafe observability label"):
        validate_label_config({"user_email": "person@example.com", "protocol": "http1"})
    with pytest.raises(ProtocolObservabilityError, match="unsafe observability label value"):
        validate_label_config({"protocol": "x" * 129, "transport": "tcp"})


def test_observability_certification_evidence_links() -> None:
    links = certification_evidence_links(
        evidence_id="evd:protocol-aware-observability-test-plan",
        protocol_claim_ids=("clm:http3-runtime", "clm:webtransport-runtime"),
        transport_claim_ids=("clm:quic-transport",),
    )

    assert links == {
        "evidence_id": "evd:protocol-aware-observability-test-plan",
        "protocol_claim_ids": ("clm:http3-runtime", "clm:webtransport-runtime"),
        "transport_claim_ids": ("clm:quic-transport",),
    }
    with pytest.raises(ProtocolObservabilityError, match="protocol and transport claim links"):
        certification_evidence_links(
            evidence_id="evd:missing",
            protocol_claim_ids=(),
            transport_claim_ids=("clm:quic-transport",),
        )
