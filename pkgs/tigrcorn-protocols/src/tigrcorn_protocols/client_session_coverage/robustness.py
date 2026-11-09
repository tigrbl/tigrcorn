from __future__ import annotations

from typing import Any

from .matrix import build_matrix_row
from .models import ClientSession, ClientTopology, CoverageDisposition, ProtocolCarrier, SessionScope


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
            self.fail_closed(client_id, connection_id, session_id, ClientTopology.CONCURRENT_CLIENTS, "max_sessions_exceeded")
            raise BufferError("session pressure budget exceeded")
        if session_id in self.sessions and not self.sessions[session_id].closed:
            self.fail_closed(client_id, connection_id, session_id, ClientTopology.CONCURRENT_CLIENTS, "duplicate_session")
            raise ValueError("duplicate session rejected")
        self.sessions[session_id] = ClientSession(client_id=client_id, connection_id=connection_id, session_id=session_id)

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
            self.fail_closed(client_id, connection_id, session_id, topology, "message_pressure_budget_exceeded", **identifiers)
            raise BufferError("message pressure budget exceeded")
        if datagram_id is not None and payload_size > self.max_datagram_size:
            self.fail_closed(client_id, connection_id, session_id, topology, "datagram_pressure_budget_exceeded", **identifiers)
            raise BufferError("datagram pressure budget exceeded")
        if len(session.payloads) >= self.max_queue:
            self.fail_closed(client_id, connection_id, session_id, topology, "queue_pressure_budget_exceeded", **identifiers)
            raise BufferError("queue pressure budget exceeded")
        if stream_id is not None:
            session.streams_seen.add(str(stream_id))
            if len(session.streams_seen) > self.max_streams:
                self.fail_closed(client_id, connection_id, session_id, topology, "max_streams_exceeded", **identifiers)
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
            self.fail_closed(client_id, connection_id, session_id, topology, "cross_client_session_access")
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
