from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class ProtocolCarrier(str, Enum):
    HTTP1 = "http1"
    HTTP2 = "http2"
    HTTP3_QUIC = "http3_quic"
    WEBSOCKET_H1 = "websocket_h1"
    WEBSOCKET_H2 = "websocket_h2"
    WEBSOCKET_H3 = "websocket_h3"
    WEBTRANSPORT_H3_QUIC = "webtransport_h3_quic"


class ClientTopology(str, Enum):
    SINGLE_CLIENT = "single_client"
    SEQUENTIAL_CLIENTS = "sequential_clients"
    BOUNDED_INTERLEAVED_CLIENTS = "bounded_interleaved_clients"
    CONCURRENT_CLIENTS = "concurrent_clients"
    CHURN_CLIENTS = "churn_clients"


class SessionScope(str, Enum):
    REQUEST_SCOPED = "request_scoped"
    TCP_CONNECTION_SCOPED = "tcp_connection_scoped"
    H2_CONNECTION_SCOPED = "h2_connection_scoped"
    H2_STREAM_SCOPED = "h2_stream_scoped"
    QUIC_CONNECTION_SCOPED = "quic_connection_scoped"
    H3_STREAM_SCOPED = "h3_stream_scoped"
    WEBSOCKET_CONNECTION_SCOPED = "websocket_connection_scoped"
    WEBTRANSPORT_SESSION_SCOPED = "webtransport_session_scoped"
    WEBTRANSPORT_STREAM_SCOPED = "webtransport_stream_scoped"
    WEBTRANSPORT_DATAGRAM_SCOPED = "webtransport_datagram_scoped"


class CoverageDisposition(str, Enum):
    COVERED = "covered"
    REQUIRED = "required"
    PLANNED = "planned"
    NOT_APPLICABLE = "not_applicable"
    FAIL_CLOSED = "fail_closed"


class BehaviorAxis(str, Enum):
    LIFECYCLE = "lifecycle_behavior"
    IDENTITY_ISOLATION = "identity_isolation"
    ORDERING = "ordering_behavior"
    PRESSURE = "pressure_mode"
    FAULT = "fault_mode"


PROTOCOL_CARRIER_VALUES = frozenset(item.value for item in ProtocolCarrier)
CLIENT_TOPOLOGY_VALUES = frozenset(item.value for item in ClientTopology)
SESSION_SCOPE_VALUES = frozenset(item.value for item in SessionScope)
DISPOSITION_VALUES = frozenset(item.value for item in CoverageDisposition)
BEHAVIOR_AXIS_VALUES = frozenset(item.value for item in BehaviorAxis)

GOVERNED_IDENTIFIER_FIELDS = frozenset(
    {
        "client_id",
        "connection_id",
        "session_id",
        "stream_id",
        "datagram_id",
    }
)
INTERNAL_ONLY_FIELDS = frozenset({"lane"})

REQUIRED_MATRIX_AXES = frozenset(
    {
        "protocol_carrier",
        "client_topology",
        "session_scope",
        "lifecycle_behavior",
        "identity_isolation",
        "ordering_behavior",
        "pressure_mode",
        "fault_mode",
        "disposition",
    }
)

PROTOCOL_CARRIER_DEFAULT_SCOPES: dict[str, SessionScope] = {
    ProtocolCarrier.HTTP1.value: SessionScope.REQUEST_SCOPED,
    ProtocolCarrier.HTTP2.value: SessionScope.H2_STREAM_SCOPED,
    ProtocolCarrier.HTTP3_QUIC.value: SessionScope.H3_STREAM_SCOPED,
    ProtocolCarrier.WEBSOCKET_H1.value: SessionScope.WEBSOCKET_CONNECTION_SCOPED,
    ProtocolCarrier.WEBSOCKET_H2.value: SessionScope.WEBSOCKET_CONNECTION_SCOPED,
    ProtocolCarrier.WEBSOCKET_H3.value: SessionScope.WEBSOCKET_CONNECTION_SCOPED,
    ProtocolCarrier.WEBTRANSPORT_H3_QUIC.value: SessionScope.WEBTRANSPORT_SESSION_SCOPED,
}


def _enum_value(value: object) -> str:
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


def _normalized(value: object) -> str:
    return str(value).strip().lower().replace("-", "_").replace(".", "_")


def classify_default_session_scope(protocol_carrier: object) -> SessionScope:
    carrier = _normalized(_enum_value(protocol_carrier))
    try:
        return PROTOCOL_CARRIER_DEFAULT_SCOPES[carrier]
    except KeyError as exc:
        raise ValueError(f"unknown protocol carrier: {protocol_carrier!r}") from exc


def validate_no_internal_lane(record: Mapping[str, Any]) -> None:
    if INTERNAL_ONLY_FIELDS.intersection(record):
        raise ValueError("lane is protocol-internal and not a governed proof field")


def validate_governed_identifiers(record: Mapping[str, Any]) -> None:
    validate_no_internal_lane(record)
    for field in GOVERNED_IDENTIFIER_FIELDS:
        if field in record and record[field] is None:
            raise ValueError(f"{field} must be omitted or populated")


def validate_matrix_row(row: Mapping[str, Any]) -> None:
    validate_governed_identifiers(row)
    missing = sorted(REQUIRED_MATRIX_AXES.difference(row))
    if missing:
        raise ValueError(f"client-session matrix row missing axes: {missing}")

    carrier = _normalized(row["protocol_carrier"])
    if carrier not in PROTOCOL_CARRIER_VALUES:
        raise ValueError(f"unknown protocol carrier: {row['protocol_carrier']!r}")

    topology = _enum_value(row["client_topology"])
    if topology not in CLIENT_TOPOLOGY_VALUES:
        raise ValueError(f"unknown client topology: {topology!r}")

    scope = _enum_value(row["session_scope"])
    if scope not in SESSION_SCOPE_VALUES:
        raise ValueError(f"unknown session scope: {scope!r}")

    disposition = _enum_value(row["disposition"])
    if disposition not in DISPOSITION_VALUES:
        raise ValueError(f"unknown disposition: {disposition!r}")

    for axis in BehaviorAxis:
        axis_value = _enum_value(row[axis.value])
        if axis_value not in DISPOSITION_VALUES:
            raise ValueError(f"{axis.value} must be a coverage disposition")


def build_matrix_row(
    *,
    protocol_carrier: ProtocolCarrier | str,
    client_topology: ClientTopology | str,
    session_scope: SessionScope | str | None = None,
    disposition: CoverageDisposition | str = CoverageDisposition.REQUIRED,
    lifecycle_behavior: CoverageDisposition | str = CoverageDisposition.REQUIRED,
    identity_isolation: CoverageDisposition | str = CoverageDisposition.REQUIRED,
    ordering_behavior: CoverageDisposition | str = CoverageDisposition.REQUIRED,
    pressure_mode: CoverageDisposition | str = CoverageDisposition.REQUIRED,
    fault_mode: CoverageDisposition | str = CoverageDisposition.REQUIRED,
    **identifiers: Any,
) -> dict[str, Any]:
    carrier = _normalized(_enum_value(protocol_carrier))
    row: dict[str, Any] = {
        "protocol_carrier": carrier,
        "client_topology": _enum_value(client_topology),
        "session_scope": _enum_value(session_scope or classify_default_session_scope(carrier)),
        "lifecycle_behavior": _enum_value(lifecycle_behavior),
        "identity_isolation": _enum_value(identity_isolation),
        "ordering_behavior": _enum_value(ordering_behavior),
        "pressure_mode": _enum_value(pressure_mode),
        "fault_mode": _enum_value(fault_mode),
        "disposition": _enum_value(disposition),
    }
    row.update(identifiers)
    validate_matrix_row(row)
    return row


@dataclass
class ClientSession:
    client_id: str
    connection_id: str
    session_id: str
    closed: bool = False
    payloads: list[str] = field(default_factory=list)


class ClientSessionTopologyHarness:
    """Runtime-facing carrier topology recorder for governed proof rows."""

    def __init__(self, carrier: ProtocolCarrier, scope: SessionScope | None = None) -> None:
        self.carrier = carrier
        self.scope = scope
        self.sessions: dict[str, ClientSession] = {}
        self.events: list[dict[str, Any]] = []

    def open(self, client_id: str, connection_id: str, session_id: str, topology: ClientTopology) -> None:
        self.sessions[session_id] = ClientSession(
            client_id=client_id,
            connection_id=connection_id,
            session_id=session_id,
        )
        self.events.append(self.record("open", client_id, connection_id, session_id, topology))

    def send(
        self,
        client_id: str,
        connection_id: str,
        session_id: str,
        topology: ClientTopology,
        payload: str,
        **identifiers: Any,
    ) -> None:
        session = self.session_for(client_id, connection_id, session_id)
        session.payloads.append(payload)
        self.events.append(
            self.record(
                "send",
                client_id,
                connection_id,
                session_id,
                topology,
                payload=payload,
                **identifiers,
            )
        )

    async def send_async(
        self,
        client_id: str,
        connection_id: str,
        session_id: str,
        topology: ClientTopology,
        payload: str,
        delay: float = 0.0,
        **identifiers: Any,
    ) -> None:
        await asyncio.sleep(delay)
        self.send(client_id, connection_id, session_id, topology, payload, **identifiers)

    def close(self, client_id: str, connection_id: str, session_id: str, topology: ClientTopology) -> None:
        session = self.session_for(client_id, connection_id, session_id)
        session.closed = True
        self.events.append(self.record("close", client_id, connection_id, session_id, topology))

    def record(
        self,
        subevent: str,
        client_id: str,
        connection_id: str,
        session_id: str,
        topology: ClientTopology,
        **extra: Any,
    ) -> dict[str, Any]:
        return build_matrix_row(
            protocol_carrier=self.carrier,
            client_topology=topology,
            session_scope=self.scope,
            disposition=CoverageDisposition.COVERED,
            lifecycle_behavior=CoverageDisposition.COVERED,
            identity_isolation=CoverageDisposition.COVERED,
            ordering_behavior=CoverageDisposition.COVERED,
            pressure_mode=CoverageDisposition.REQUIRED,
            fault_mode=CoverageDisposition.REQUIRED,
            client_id=client_id,
            connection_id=connection_id,
            session_id=session_id,
            subevent=subevent,
            **extra,
        )

    def session_for(self, client_id: str, connection_id: str, session_id: str) -> ClientSession:
        session = self.sessions[session_id]
        if session.client_id != client_id or session.connection_id != connection_id:
            raise PermissionError("cross-client or cross-connection session access rejected")
        if session.closed:
            raise RuntimeError("post-close send rejected")
        return session


def sequential_pair(carrier: ProtocolCarrier, scope: SessionScope | None = None) -> ClientSessionTopologyHarness:
    topology = ClientTopology.SEQUENTIAL_CLIENTS
    harness = ClientSessionTopologyHarness(carrier, scope)
    harness.open("client-a", "conn-a", "session-a", topology)
    harness.send("client-a", "conn-a", "session-a", topology, "a-1")
    harness.close("client-a", "conn-a", "session-a", topology)
    harness.open("client-b", "conn-b", "session-b", topology)
    harness.send("client-b", "conn-b", "session-b", topology, "b-1")
    harness.close("client-b", "conn-b", "session-b", topology)
    return harness


def bounded_interleaved_pair(
    carrier: ProtocolCarrier,
    scope: SessionScope | None = None,
) -> ClientSessionTopologyHarness:
    topology = ClientTopology.BOUNDED_INTERLEAVED_CLIENTS
    harness = ClientSessionTopologyHarness(carrier, scope)
    harness.open("client-a", "conn-a", "session-a", topology)
    harness.open("client-b", "conn-b", "session-b", topology)
    for client_id, connection_id, session_id, payload in (
        ("client-a", "conn-a", "session-a", "a-1"),
        ("client-b", "conn-b", "session-b", "b-1"),
        ("client-a", "conn-a", "session-a", "a-2"),
        ("client-b", "conn-b", "session-b", "b-2"),
    ):
        harness.send(client_id, connection_id, session_id, topology, payload)
    return harness


__all__ = [
    "BEHAVIOR_AXIS_VALUES",
    "CLIENT_TOPOLOGY_VALUES",
    "DISPOSITION_VALUES",
    "GOVERNED_IDENTIFIER_FIELDS",
    "INTERNAL_ONLY_FIELDS",
    "PROTOCOL_CARRIER_DEFAULT_SCOPES",
    "PROTOCOL_CARRIER_VALUES",
    "REQUIRED_MATRIX_AXES",
    "SESSION_SCOPE_VALUES",
    "BehaviorAxis",
    "ClientSession",
    "ClientSessionTopologyHarness",
    "ClientTopology",
    "CoverageDisposition",
    "ProtocolCarrier",
    "SessionScope",
    "build_matrix_row",
    "bounded_interleaved_pair",
    "classify_default_session_scope",
    "sequential_pair",
    "validate_governed_identifiers",
    "validate_matrix_row",
    "validate_no_internal_lane",
]
