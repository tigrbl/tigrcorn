from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


class WebTransportGovernanceError(ValueError):
    """Raised when WebTransport resource governance fails closed."""


@dataclass(frozen=True, slots=True)
class WebTransportBudgetPolicy:
    max_streams: int
    max_datagram_size: int
    max_datagrams_per_session: int
    max_memory_bytes: int
    max_bandwidth_bytes: int
    max_peers: int
    datagram_abuse_threshold: int = 2

    def as_dict(self) -> dict[str, int]:
        return {
            "datagram_abuse_threshold": self.datagram_abuse_threshold,
            "max_bandwidth_bytes": self.max_bandwidth_bytes,
            "max_datagram_size": self.max_datagram_size,
            "max_datagrams_per_session": self.max_datagrams_per_session,
            "max_memory_bytes": self.max_memory_bytes,
            "max_peers": self.max_peers,
            "max_streams": self.max_streams,
        }


@dataclass(slots=True)
class WebTransportSessionBudget:
    session_id: str
    peer_id: str
    streams: set[str] = field(default_factory=set)
    datagrams: int = 0
    datagram_abuse_events: int = 0
    memory_bytes: int = 0
    bandwidth_bytes: int = 0
    closed: bool = False
    close_reason: str | None = None
    address: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "address": self.address,
            "bandwidth_bytes": self.bandwidth_bytes,
            "closed": self.closed,
            "close_reason": self.close_reason,
            "datagram_abuse_events": self.datagram_abuse_events,
            "datagrams": self.datagrams,
            "memory_bytes": self.memory_bytes,
            "peer_id": self.peer_id,
            "session_id": self.session_id,
            "streams": tuple(sorted(self.streams)),
        }


@dataclass(slots=True)
class WebTransportGovernanceManager:
    policy: WebTransportBudgetPolicy
    sessions: dict[str, WebTransportSessionBudget] = field(default_factory=dict)
    peers: set[str] = field(default_factory=set)
    released_sessions: set[str] = field(default_factory=set)

    def open_session(self, session_id: str, *, peer_id: str, address: str | None = None) -> dict[str, Any]:
        if session_id in self.sessions and not self.sessions[session_id].closed:
            session = self.sessions[session_id]
            if address is not None:
                session.address = address
            return session.as_dict()
        next_peers = set(self.peers)
        next_peers.add(peer_id)
        if len(next_peers) > self.policy.max_peers:
            raise WebTransportGovernanceError("peer budget exceeded")
        session = WebTransportSessionBudget(session_id=session_id, peer_id=peer_id, address=address)
        self.sessions[session_id] = session
        self.peers = next_peers
        self.released_sessions.discard(session_id)
        return session.as_dict()

    def open_stream(self, session_id: str, stream_id: str) -> dict[str, Any]:
        session = self._active_session(session_id)
        if stream_id not in session.streams and len(session.streams) >= self.policy.max_streams:
            raise WebTransportGovernanceError("stream budget exceeded")
        session.streams.add(stream_id)
        return session.as_dict()

    def close_stream(self, session_id: str, stream_id: str) -> dict[str, Any]:
        session = self._active_session(session_id)
        session.streams.discard(stream_id)
        return session.as_dict()

    def send_datagram(self, session_id: str, datagram_id: str, payload: bytes) -> dict[str, Any]:
        session = self._active_session(session_id)
        if len(payload) > self.policy.max_datagram_size:
            return self._record_datagram_abuse(session, datagram_id, "datagram size budget exceeded")
        if session.datagrams >= self.policy.max_datagrams_per_session:
            return self._record_datagram_abuse(session, datagram_id, "datagram count budget exceeded")
        session.datagrams += 1
        session.bandwidth_bytes += len(payload)
        if session.bandwidth_bytes > self.policy.max_bandwidth_bytes:
            self.close_session(session.session_id, reason="bandwidth budget exceeded")
            raise WebTransportGovernanceError("bandwidth budget exceeded")
        return {
            "accepted": True,
            "datagram_id": datagram_id,
            "session": session.as_dict(),
        }

    def allocate_memory(self, session_id: str, amount: int) -> dict[str, Any]:
        if amount < 0:
            raise WebTransportGovernanceError("memory budget amount must be non-negative")
        session = self._active_session(session_id)
        if session.memory_bytes + amount > self.policy.max_memory_bytes:
            self.close_session(session_id, reason="memory budget exceeded")
            raise WebTransportGovernanceError("memory budget exceeded")
        session.memory_bytes += amount
        return session.as_dict()

    def fair_flow_control(
        self,
        demands: Mapping[str, Mapping[str, int]],
        *,
        total_credit: int,
    ) -> dict[str, dict[str, int]]:
        if total_credit < 0:
            raise WebTransportGovernanceError("flow-control credit must be non-negative")
        active_sessions = [
            session_id
            for session_id in sorted(demands)
            if session_id in self.sessions and not self.sessions[session_id].closed
        ]
        if not active_sessions:
            return {}
        session_credit = total_credit // len(active_sessions)
        allocations: dict[str, dict[str, int]] = {}
        for session_id in active_sessions:
            streams = demands[session_id]
            if not streams:
                allocations[session_id] = {}
                continue
            stream_credit = max(1, session_credit // len(streams))
            allocations[session_id] = {
                stream_id: min(int(requested), stream_credit)
                for stream_id, requested in sorted(streams.items())
            }
        return allocations

    def migrate_session(self, session_id: str, *, new_address: str) -> dict[str, Any]:
        session = self._active_session(session_id)
        session.address = new_address
        return session.as_dict()

    def close_session(self, session_id: str, *, reason: str) -> dict[str, Any]:
        session = self.sessions.get(session_id)
        if session is None:
            raise WebTransportGovernanceError("unknown WebTransport session")
        session.closed = True
        session.close_reason = reason
        session.streams.clear()
        session.memory_bytes = 0
        self.released_sessions.add(session_id)
        if not any(not item.closed and item.peer_id == session.peer_id for item in self.sessions.values()):
            self.peers.discard(session.peer_id)
        return session.as_dict()

    def snapshot(self) -> dict[str, Any]:
        return {
            "active_sessions": tuple(sorted(session_id for session_id, session in self.sessions.items() if not session.closed)),
            "peers": tuple(sorted(self.peers)),
            "policy": self.policy.as_dict(),
            "released_sessions": tuple(sorted(self.released_sessions)),
            "sessions": {
                session_id: self.sessions[session_id].as_dict()
                for session_id in sorted(self.sessions)
            },
        }

    def _record_datagram_abuse(
        self,
        session: WebTransportSessionBudget,
        datagram_id: str,
        reason: str,
    ) -> dict[str, Any]:
        session.datagram_abuse_events += 1
        if session.datagram_abuse_events >= self.policy.datagram_abuse_threshold:
            close_snapshot = self.close_session(session.session_id, reason=reason)
            return {
                "accepted": False,
                "closed": True,
                "datagram_id": datagram_id,
                "reason": reason,
                "session": close_snapshot,
            }
        return {
            "accepted": False,
            "closed": False,
            "datagram_id": datagram_id,
            "reason": reason,
            "session": session.as_dict(),
        }

    def _active_session(self, session_id: str) -> WebTransportSessionBudget:
        session = self.sessions.get(session_id)
        if session is None:
            raise WebTransportGovernanceError("unknown WebTransport session")
        if session.closed:
            raise WebTransportGovernanceError("WebTransport session is closed")
        return session


def default_webtransport_budget_policy() -> WebTransportBudgetPolicy:
    return WebTransportBudgetPolicy(
        max_streams=16,
        max_datagram_size=1200,
        max_datagrams_per_session=128,
        max_memory_bytes=1_048_576,
        max_bandwidth_bytes=16_777_216,
        max_peers=64,
    )


def export_webtransport_governance_config(
    policy: WebTransportBudgetPolicy | None = None,
) -> dict[str, Any]:
    selected = default_webtransport_budget_policy() if policy is None else policy
    return {
        "budget_model": {
            "bandwidth": selected.max_bandwidth_bytes,
            "datagrams": {
                "max_count_per_session": selected.max_datagrams_per_session,
                "max_size": selected.max_datagram_size,
            },
            "memory": selected.max_memory_bytes,
            "peers": selected.max_peers,
            "streams": selected.max_streams,
        },
        "policy": selected.as_dict(),
        "schema_version": 1,
        "surface": "tigrcorn.webtransport.resource-governance",
    }


def certify_webtransport_resource_governance(
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    if not evidence.get("budget_policy"):
        raise WebTransportGovernanceError("WebTransport certification requires explicit resource policy")
    required = ("stream_limit", "datagram_limit", "memory_limit", "peer_limit", "cleanup")
    missing = tuple(key for key in required if not evidence.get(key))
    if missing:
        raise WebTransportGovernanceError(
            "missing WebTransport resource-governance evidence: " + ", ".join(missing)
        )
    return {
        "certification_state": "certified",
        "evidence_keys": tuple(sorted(evidence)),
        "required_evidence": required,
    }
