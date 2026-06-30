from __future__ import annotations

from dataclasses import dataclass, field
from time import monotonic
from typing import Any, Mapping


ConnectionState = str
ProtocolSessionState = str


def peer_id_from_address(address: str | None) -> str:
    if not address:
        return "peer:unknown"
    return f"peer:addr:{address}"


@dataclass(slots=True)
class PeerIdentity:
    peer_id: str
    kind: str = "address"
    address: str | None = None
    connection_ids: set[str] = field(default_factory=set)
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "address": self.address,
            "connection_ids": sorted(self.connection_ids),
            "kind": self.kind,
            "metadata": _jsonable(self.metadata),
            "peer_id": self.peer_id,
        }


@dataclass(slots=True)
class ConnectionRecord:
    connection_id: str
    transport: str
    protocols: tuple[str, ...]
    listener_id: str
    peer_id: str
    remote_address: str | None = None
    local_address: str | None = None
    opened_at: float = field(default_factory=monotonic)
    closed_at: float | None = None
    state: ConnectionState = "open"
    counters: dict[str, int] = field(default_factory=dict)
    security: dict[str, Any] = field(default_factory=dict)
    session_ids: set[str] = field(default_factory=set)

    def as_dict(self) -> dict[str, Any]:
        return {
            "closed_at": self.closed_at,
            "connection_id": self.connection_id,
            "counters": {key: self.counters[key] for key in sorted(self.counters)},
            "listener_id": self.listener_id,
            "local_address": self.local_address,
            "opened_at": self.opened_at,
            "peer_id": self.peer_id,
            "protocols": sorted(self.protocols),
            "remote_address": self.remote_address,
            "security": _jsonable(self.security),
            "session_ids": sorted(self.session_ids),
            "state": self.state,
            "transport": self.transport,
        }


@dataclass(slots=True)
class ProtocolSessionRecord:
    session_id: str
    connection_id: str
    kind: str
    state: ProtocolSessionState = "open"
    stream_ids: set[str] = field(default_factory=set)
    counters: dict[str, int] = field(default_factory=dict)
    close_reason: str | None = None
    opened_at: float = field(default_factory=monotonic)
    closed_at: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "closed_at": self.closed_at,
            "close_reason": self.close_reason,
            "connection_id": self.connection_id,
            "counters": {key: self.counters[key] for key in sorted(self.counters)},
            "kind": self.kind,
            "metadata": _jsonable(self.metadata),
            "opened_at": self.opened_at,
            "session_id": self.session_id,
            "state": self.state,
            "stream_ids": sorted(self.stream_ids),
        }


@dataclass(slots=True)
class RuntimeConnectionInventory:
    peers: dict[str, PeerIdentity] = field(default_factory=dict)
    connections: dict[str, ConnectionRecord] = field(default_factory=dict)
    sessions: dict[str, ProtocolSessionRecord] = field(default_factory=dict)

    def open_connection(
        self,
        connection_id: str,
        *,
        transport: str,
        protocols: tuple[str, ...],
        listener_id: str,
        peer_id: str,
        remote_address: str | None = None,
        local_address: str | None = None,
        security: Mapping[str, Any] | None = None,
        peer_kind: str = "address",
        peer_metadata: Mapping[str, Any] | None = None,
    ) -> ConnectionRecord:
        peer = self.peers.get(peer_id)
        if peer is None:
            peer = PeerIdentity(
                peer_id=peer_id,
                kind=peer_kind,
                address=remote_address,
                metadata=dict(peer_metadata or {}),
            )
            self.peers[peer_id] = peer
        if remote_address is not None:
            peer.address = remote_address
        peer.connection_ids.add(connection_id)
        record = self.connections.get(connection_id)
        if record is None:
            record = ConnectionRecord(
                connection_id=connection_id,
                transport=transport,
                protocols=tuple(protocols),
                listener_id=listener_id,
                peer_id=peer_id,
                remote_address=remote_address,
                local_address=local_address,
                security=dict(security or {}),
            )
            self.connections[connection_id] = record
        else:
            record.transport = transport
            record.protocols = tuple(protocols)
            record.listener_id = listener_id
            record.peer_id = peer_id
            record.remote_address = remote_address
            record.local_address = local_address
            record.security.update(dict(security or {}))
            record.state = "open"
            record.closed_at = None
        return record

    def update_connection(
        self,
        connection_id: str,
        *,
        state: str | None = None,
        remote_address: str | None = None,
        local_address: str | None = None,
        counters: Mapping[str, int] | None = None,
        security: Mapping[str, Any] | None = None,
    ) -> ConnectionRecord | None:
        record = self.connections.get(connection_id)
        if record is None:
            return None
        if state is not None:
            record.state = state
        if remote_address is not None:
            record.remote_address = remote_address
            peer = self.peers.get(record.peer_id)
            if peer is not None:
                peer.address = remote_address
        if local_address is not None:
            record.local_address = local_address
        if counters is not None:
            for key, value in counters.items():
                record.counters[key] = int(value)
        if security is not None:
            record.security.update(dict(security))
        return record

    def increment_connection_counter(self, connection_id: str, key: str, amount: int = 1) -> None:
        record = self.connections.get(connection_id)
        if record is None:
            return
        record.counters[key] = record.counters.get(key, 0) + int(amount)

    def close_connection(self, connection_id: str, *, reason: str | None = None) -> ConnectionRecord | None:
        record = self.connections.get(connection_id)
        if record is None:
            return None
        if record.closed_at is None:
            record.closed_at = monotonic()
        record.state = "closed"
        if reason:
            record.security.setdefault("close_reason", reason)
        return record

    def open_session(
        self,
        session_id: str,
        *,
        connection_id: str,
        kind: str,
        stream_ids: tuple[str, ...] = (),
        metadata: Mapping[str, Any] | None = None,
    ) -> ProtocolSessionRecord:
        record = self.sessions.get(session_id)
        if record is None:
            record = ProtocolSessionRecord(
                session_id=session_id,
                connection_id=connection_id,
                kind=kind,
                stream_ids=set(stream_ids),
                metadata=dict(metadata or {}),
            )
            self.sessions[session_id] = record
        else:
            record.connection_id = connection_id
            record.kind = kind
            record.stream_ids.update(stream_ids)
            record.metadata.update(dict(metadata or {}))
            record.state = "open"
            record.closed_at = None
            record.close_reason = None
        connection = self.connections.get(connection_id)
        if connection is not None:
            connection.session_ids.add(session_id)
        return record

    def update_session(
        self,
        session_id: str,
        *,
        state: str | None = None,
        stream_ids: tuple[str, ...] = (),
        counters: Mapping[str, int] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> ProtocolSessionRecord | None:
        record = self.sessions.get(session_id)
        if record is None:
            return None
        if state is not None:
            record.state = state
        record.stream_ids.update(stream_ids)
        if counters is not None:
            for key, value in counters.items():
                record.counters[key] = int(value)
        if metadata is not None:
            record.metadata.update(dict(metadata))
        return record

    def increment_session_counter(self, session_id: str, key: str, amount: int = 1) -> None:
        record = self.sessions.get(session_id)
        if record is None:
            return
        record.counters[key] = record.counters.get(key, 0) + int(amount)

    def close_session(self, session_id: str, *, reason: str | None = None) -> ProtocolSessionRecord | None:
        record = self.sessions.get(session_id)
        if record is None:
            return None
        if record.closed_at is None:
            record.closed_at = monotonic()
        record.state = "closed"
        record.close_reason = reason
        return record

    def snapshot(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "counts": {
                "active_connections": sum(1 for record in self.connections.values() if record.state != "closed"),
                "active_peers": sum(1 for peer in self.peers.values() if any(self.connections.get(cid) and self.connections[cid].state != "closed" for cid in peer.connection_ids)),
                "active_sessions": sum(1 for record in self.sessions.values() if record.state != "closed"),
                "connections": len(self.connections),
                "peers": len(self.peers),
                "sessions": len(self.sessions),
            },
            "connections": {
                connection_id: self.connections[connection_id].as_dict()
                for connection_id in sorted(self.connections)
            },
            "peers": {
                peer_id: self.peers[peer_id].as_dict()
                for peer_id in sorted(self.peers)
            },
            "sessions": {
                session_id: self.sessions[session_id].as_dict()
                for session_id in sorted(self.sessions)
            },
        }


def _jsonable(value: Any) -> Any:
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, set):
        return sorted(_jsonable(item) for item in value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in sorted(value.items(), key=lambda item: str(item[0]))}
    return value


__all__ = [
    "ConnectionRecord",
    "PeerIdentity",
    "ProtocolSessionRecord",
    "RuntimeConnectionInventory",
    "peer_id_from_address",
]
