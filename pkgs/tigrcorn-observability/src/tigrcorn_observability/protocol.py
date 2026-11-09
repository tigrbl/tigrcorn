from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Mapping


class ProtocolObservabilityError(ValueError):
    """Raised when protocol-aware observability would emit unsafe telemetry."""


PROTOCOL_LABEL_SCHEMA: tuple[tuple[str, str], ...] = (
    ("protocol", "low-cardinality protocol name"),
    ("transport", "low-cardinality transport domain"),
    ("tls_version", "safe TLS protocol version"),
    ("alpn", "safe negotiated ALPN token"),
    ("profile", "deployment profile"),
    ("listener_id", "bounded listener identifier"),
    ("lifecycle", "protocol lifecycle event"),
)

_ALLOWED_LABELS = {name for name, _description in PROTOCOL_LABEL_SCHEMA} | {
    "event_kind",
    "metric",
    "quic_loss_packets",
    "quic_migration",
    "quic_rtt_ms",
    "span_id",
    "trace_id",
}
_SENSITIVE_PATTERN = re.compile(r"(authorization|certificate|cookie|key|password|private|qlog|secret|token)", re.I)
_HIGH_CARDINALITY = {"client_ip", "connection_id", "path", "peer", "peer_id", "qlog_connection_id", "session_id"}


@dataclass(frozen=True, slots=True)
class ProtocolLabels:
    protocol: str
    transport: str
    tls_version: str | None = None
    alpn: str | None = None
    profile: str | None = None
    listener_id: str | None = None
    lifecycle: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        return {
            "alpn": self.alpn,
            "lifecycle": self.lifecycle,
            "listener_id": self.listener_id,
            "profile": self.profile,
            "protocol": self.protocol,
            "tls_version": self.tls_version,
            "transport": self.transport,
        }


@dataclass(frozen=True, slots=True)
class ObservabilityRecord:
    kind: str
    name: str
    labels: dict[str, Any]
    attributes: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "attributes": _stable_mapping(self.attributes),
            "kind": self.kind,
            "labels": _stable_mapping(self.labels),
            "name": self.name,
            "schema_version": 1,
        }


def protocol_label_schema() -> dict[str, Any]:
    return {
        "cardinality": {
            "bounded": tuple(sorted(_ALLOWED_LABELS)),
            "hashed": tuple(sorted(_HIGH_CARDINALITY)),
        },
        "labels": tuple({"name": name, "description": description} for name, description in PROTOCOL_LABEL_SCHEMA),
        "redaction": tuple(sorted(("authorization", "certificate", "cookie", "key", "password", "private", "qlog", "secret", "token"))),
        "schema_version": 1,
    }


def make_observability_record(
    *,
    kind: str,
    name: str,
    labels: Mapping[str, Any],
    attributes: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    validated = validate_label_config(labels)
    return ObservabilityRecord(
        kind=kind,
        name=name,
        labels=redact_and_bound_labels(validated),
        attributes=redact_mapping(attributes or {}),
    ).as_dict()


def protocol_transport_labels(*, protocol: str, transport: str, profile: str = "default") -> dict[str, Any]:
    return ProtocolLabels(protocol=protocol, transport=transport, profile=profile).as_dict()


def tls_alpn_labels(*, protocol: str, transport: str, tls_version: str, alpn: str) -> dict[str, Any]:
    return ProtocolLabels(
        protocol=protocol,
        transport=transport,
        tls_version=tls_version,
        alpn=alpn,
    ).as_dict()


def lifecycle_event(*, protocol: str, transport: str, lifecycle: str, session_id: str | None = None) -> dict[str, Any]:
    labels = ProtocolLabels(protocol=protocol, transport=transport, lifecycle=lifecycle).as_dict()
    if session_id is not None:
        labels["session_id"] = session_id
    return make_observability_record(kind="event", name=f"{protocol}.{lifecycle}", labels=labels)


def propagate_otel_context(context: Mapping[str, str], labels: Mapping[str, Any]) -> dict[str, Any]:
    trace_id = context.get("traceparent", "").split("-")[1] if context.get("traceparent", "").count("-") >= 3 else None
    span_id = context.get("traceparent", "").split("-")[2] if context.get("traceparent", "").count("-") >= 3 else None
    merged = dict(labels)
    if trace_id:
        merged["trace_id"] = trace_id
    if span_id:
        merged["span_id"] = span_id
    return make_observability_record(kind="trace", name="otel.context", labels=merged)


def quic_operational_labels(*, rtt_ms: float, loss_packets: int, migration: str, qlog_secret: str | None = None) -> dict[str, Any]:
    labels: dict[str, Any] = {
        "protocol": "quic",
        "transport": "quic",
        "quic_loss_packets": max(0, int(loss_packets)),
        "quic_migration": migration,
        "quic_rtt_ms": round(float(rtt_ms), 3),
    }
    attributes: dict[str, Any] = {}
    if qlog_secret is not None:
        attributes["qlog_secret"] = qlog_secret
    return make_observability_record(kind="metric", name="quic.operational", labels=labels, attributes=attributes)


def redact_mapping(payload: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key in sorted(payload):
        value = payload[key]
        if _SENSITIVE_PATTERN.search(str(key)):
            result[key] = "[redacted]"
        elif isinstance(value, Mapping):
            result[key] = redact_mapping(value)
        else:
            result[key] = value
    return result


def redact_and_bound_labels(labels: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key in sorted(labels):
        value = labels[key]
        if _SENSITIVE_PATTERN.search(str(key)):
            result[key] = "[redacted]"
        elif key in _HIGH_CARDINALITY:
            result[f"{key}_hash"] = _hash_label(value)
        else:
            result[key] = value
    return result


def validate_label_config(labels: Mapping[str, Any]) -> dict[str, Any]:
    for key, value in labels.items():
        if _SENSITIVE_PATTERN.search(str(key)):
            continue
        if key in _HIGH_CARDINALITY:
            continue
        if key not in _ALLOWED_LABELS:
            raise ProtocolObservabilityError(f"unsafe observability label: {key}")
        if isinstance(value, str) and len(value) > 128:
            raise ProtocolObservabilityError(f"unsafe observability label value: {key}")
    return dict(labels)


def certification_evidence_links(
    *,
    evidence_id: str,
    protocol_claim_ids: tuple[str, ...],
    transport_claim_ids: tuple[str, ...],
) -> dict[str, Any]:
    if not protocol_claim_ids or not transport_claim_ids:
        raise ProtocolObservabilityError("observability evidence requires protocol and transport claim links")
    return {
        "evidence_id": evidence_id,
        "protocol_claim_ids": tuple(sorted(protocol_claim_ids)),
        "transport_claim_ids": tuple(sorted(transport_claim_ids)),
    }


def _hash_label(value: Any) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:16]


def _stable_mapping(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {key: payload[key] for key in sorted(payload)}


__all__ = [
    "ProtocolLabels",
    "ProtocolObservabilityError",
    "ObservabilityRecord",
    "certification_evidence_links",
    "lifecycle_event",
    "make_observability_record",
    "protocol_label_schema",
    "protocol_transport_labels",
    "propagate_otel_context",
    "quic_operational_labels",
    "redact_and_bound_labels",
    "redact_mapping",
    "tls_alpn_labels",
    "validate_label_config",
]
