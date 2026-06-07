from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


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


@dataclass
class ClientSession:
    client_id: str
    connection_id: str
    session_id: str
    closed: bool = False
    payloads: list[str] = field(default_factory=list)
    streams_seen: set[str] = field(default_factory=set)
    datagrams_seen: set[str] = field(default_factory=set)
