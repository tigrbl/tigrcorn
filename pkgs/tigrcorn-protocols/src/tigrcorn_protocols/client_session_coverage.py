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
    streams_seen: set[str] = field(default_factory=set)
    datagrams_seen: set[str] = field(default_factory=set)


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


class ClientSessionRobustnessHarness:
    """Carrier-aware runtime harness for T2 pressure, fault, and cleanup proof."""

    def __init__(
        self,
        carrier: ProtocolCarrier,
        scope: SessionScope | None = None,
        *,
        max_sessions: int = 32,
        max_streams: int = 32,
        max_queue: int = 32,
        max_message_size: int = 65536,
        max_datagram_size: int = 1200,
    ) -> None:
        self.carrier = carrier
        self.scope = scope
        self.max_sessions = max_sessions
        self.max_streams = max_streams
        self.max_queue = max_queue
        self.max_message_size = max_message_size
        self.max_datagram_size = max_datagram_size
        self.sessions: dict[str, ClientSession] = {}
        self.errors: list[dict[str, Any]] = []

    def open(self, client_id: str, connection_id: str, session_id: str) -> None:
        if len([session for session in self.sessions.values() if not session.closed]) >= self.max_sessions:
            self.fail_closed(
                client_id,
                connection_id,
                session_id,
                ClientTopology.CONCURRENT_CLIENTS,
                "max_sessions_exceeded",
            )
            raise BufferError("session pressure budget exceeded")
        if session_id in self.sessions and not self.sessions[session_id].closed:
            self.fail_closed(
                client_id,
                connection_id,
                session_id,
                ClientTopology.CONCURRENT_CLIENTS,
                "duplicate_session",
            )
            raise ValueError("duplicate session rejected")
        self.sessions[session_id] = ClientSession(
            client_id=client_id,
            connection_id=connection_id,
            session_id=session_id,
        )

    def send(
        self,
        client_id: str,
        connection_id: str,
        session_id: str,
        topology: ClientTopology,
        payload: object,
        *,
        stream_id: str | int | None = None,
        datagram_id: str | int | None = None,
    ) -> None:
        session = self.session_for(client_id, connection_id, session_id, topology)
        identifiers = {"stream_id": stream_id, "datagram_id": datagram_id}
        if session.closed:
            self.fail_closed(client_id, connection_id, session_id, topology, "post_close_send", **identifiers)
            raise RuntimeError("post-close send rejected")
        if not isinstance(payload, (str, bytes)) or not payload:
            self.fail_closed(client_id, connection_id, session_id, topology, "malformed_payload", **identifiers)
            raise ValueError("malformed payload rejected")
        payload_size = len(payload)
        if payload_size > self.max_message_size:
            self.fail_closed(
                client_id,
                connection_id,
                session_id,
                topology,
                "message_pressure_budget_exceeded",
                **identifiers,
            )
            raise BufferError("message pressure budget exceeded")
        if datagram_id is not None and payload_size > self.max_datagram_size:
            self.fail_closed(
                client_id,
                connection_id,
                session_id,
                topology,
                "datagram_pressure_budget_exceeded",
                **identifiers,
            )
            raise BufferError("datagram pressure budget exceeded")
        if len(session.payloads) >= self.max_queue:
            self.fail_closed(
                client_id,
                connection_id,
                session_id,
                topology,
                "queue_pressure_budget_exceeded",
                **identifiers,
            )
            raise BufferError("queue pressure budget exceeded")
        if stream_id is not None:
            session.streams_seen.add(str(stream_id))
            if len(session.streams_seen) > self.max_streams:
                self.fail_closed(
                    client_id,
                    connection_id,
                    session_id,
                    topology,
                    "max_streams_exceeded",
                    **identifiers,
                )
                session.streams_seen.remove(str(stream_id))
                raise BufferError("stream pressure budget exceeded")
        if datagram_id is not None:
            session.datagrams_seen.add(str(datagram_id))
        session.payloads.append(payload if isinstance(payload, str) else payload.decode("latin1"))

    def close(self, client_id: str, connection_id: str, session_id: str, topology: ClientTopology) -> None:
        self.session_for(client_id, connection_id, session_id, topology).closed = True

    def cancel(self, client_id: str, connection_id: str, session_id: str, topology: ClientTopology) -> None:
        self.session_for(client_id, connection_id, session_id, topology).closed = True
        self.fail_closed(client_id, connection_id, session_id, topology, "cancelled")

    def timeout(self, client_id: str, connection_id: str, session_id: str, topology: ClientTopology) -> None:
        self.session_for(client_id, connection_id, session_id, topology).closed = True
        self.fail_closed(client_id, connection_id, session_id, topology, "timeout")

    def session_for(
        self,
        client_id: str,
        connection_id: str,
        session_id: str,
        topology: ClientTopology,
    ) -> ClientSession:
        try:
            session = self.sessions[session_id]
        except KeyError as exc:
            self.fail_closed(client_id, connection_id, session_id, topology, "unknown_session")
            raise KeyError("unknown session rejected") from exc
        if session.client_id != client_id or session.connection_id != connection_id:
            self.fail_closed(
                client_id,
                connection_id,
                session_id,
                topology,
                "cross_client_session_access",
            )
            raise PermissionError("cross-client or cross-connection session access rejected")
        return session

    def fail_closed(
        self,
        client_id: str,
        connection_id: str,
        session_id: str,
        topology: ClientTopology,
        error_kind: str,
        **identifiers: Any,
    ) -> dict[str, Any]:
        identifiers = {key: value for key, value in identifiers.items() if value is not None}
        row = build_matrix_row(
            protocol_carrier=self.carrier,
            client_topology=topology,
            session_scope=self.scope,
            disposition=CoverageDisposition.FAIL_CLOSED,
            lifecycle_behavior=CoverageDisposition.COVERED,
            identity_isolation=CoverageDisposition.COVERED,
            ordering_behavior=CoverageDisposition.COVERED,
            pressure_mode=CoverageDisposition.COVERED,
            fault_mode=CoverageDisposition.COVERED,
            client_id=client_id,
            connection_id=connection_id,
            session_id=session_id,
            error_kind=error_kind,
            **identifiers,
        )
        self.errors.append(row)
        return row


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
    "ClientSessionRobustnessHarness",
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
