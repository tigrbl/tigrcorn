from __future__ import annotations

import asyncio
from typing import Any

from .matrix import build_matrix_row
from .models import ClientSession, ClientTopology, CoverageDisposition, ProtocolCarrier, SessionScope


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
