from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from time import monotonic
from typing import Any


RESUMABLE_BINDINGS = frozenset(
    {"h11", "h2", "http.stream", "http.sse", "ws", "wss", "webtransport"}
)


class ResumeState(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    RESUMED = "resumed"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class StreamResumeIdentity:
    client_id: str
    session_id: str
    stream_id: str
    binding: str

    def __post_init__(self) -> None:
        for name, value in (
            ("client_id", self.client_id),
            ("session_id", self.session_id),
            ("stream_id", self.stream_id),
            ("binding", self.binding),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} is required")
        if self.binding not in RESUMABLE_BINDINGS:
            raise ValueError(f"binding {self.binding!r} is not resumable")

    def as_dict(self) -> dict[str, str]:
        return {
            "client_id": self.client_id,
            "session_id": self.session_id,
            "stream_id": self.stream_id,
            "binding": self.binding,
        }


@dataclass(slots=True)
class StreamResumeRecord:
    token: str
    identity: StreamResumeIdentity
    base_offset: int = 0
    next_offset: int = 0
    state: ResumeState = ResumeState.ACTIVE
    expires_at: float | None = None
    replay_units: list[bytes] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not isinstance(self.token, str) or not self.token:
            raise ValueError("resume token is required")
        if self.base_offset < 0:
            raise ValueError("base_offset must be non-negative")
        if self.next_offset < 0:
            raise ValueError("next_offset must be non-negative")
        if self.base_offset > self.next_offset:
            raise ValueError("base_offset cannot exceed next_offset")

    def expired(self, *, now: float | None = None) -> bool:
        return self.expires_at is not None and (now if now is not None else monotonic()) >= self.expires_at

    def snapshot(self) -> dict[str, Any]:
        return {
            "token": self.token,
            "identity": self.identity.as_dict(),
            "base_offset": self.base_offset,
            "next_offset": self.next_offset,
            "state": self.state.value,
            "replay_count": len(self.replay_units),
        }


@dataclass(frozen=True, slots=True)
class ResumeDecision:
    accepted: bool
    token: str
    state: ResumeState
    identity: StreamResumeIdentity | None = None
    reason: str | None = None
    accepted_offset: int | None = None
    replay_units: tuple[bytes, ...] = ()

    def event(self) -> dict[str, Any]:
        event_type = "stream.resume.accept" if self.accepted else "stream.resume.reject"
        payload: dict[str, Any] = {
            "type": event_type,
            "resume_token": self.token,
        }
        if self.identity is not None:
            payload.update(self.identity.as_dict())
        if self.accepted:
            payload["accepted_offset"] = self.accepted_offset or 0
            payload["replay_count"] = len(self.replay_units)
        else:
            payload["reason"] = self.reason or self.state.value
        return payload


class StreamResumeRegistry:
    def __init__(self, *, max_replay_units: int = 1024) -> None:
        if max_replay_units < 1:
            raise ValueError("max_replay_units must be positive")
        self.max_replay_units = max_replay_units
        self._records: dict[str, StreamResumeRecord] = {}

    def register(
        self,
        *,
        token: str,
        identity: StreamResumeIdentity,
        ttl_seconds: float | None = None,
        now: float | None = None,
    ) -> StreamResumeRecord:
        expires_at = None
        if ttl_seconds is not None:
            if ttl_seconds <= 0:
                raise ValueError("ttl_seconds must be positive")
            expires_at = (now if now is not None else monotonic()) + ttl_seconds
        record = StreamResumeRecord(token=token, identity=identity, expires_at=expires_at)
        self._records[token] = record
        return record

    def record_replay_unit(self, token: str, data: bytes) -> None:
        record = self._records[token]
        if not isinstance(data, bytes):
            raise ValueError("replay unit must be bytes")
        if len(record.replay_units) >= self.max_replay_units:
            record.replay_units.pop(0)
            record.base_offset += 1
        record.replay_units.append(data)
        record.next_offset += 1

    def suspend(self, token: str) -> StreamResumeRecord:
        record = self._records[token]
        record.state = ResumeState.SUSPENDED
        return record

    def resume(
        self,
        *,
        token: str,
        identity: StreamResumeIdentity,
        requested_offset: int = 0,
        now: float | None = None,
    ) -> ResumeDecision:
        record = self._records.get(token)
        if record is None:
            return ResumeDecision(False, token, ResumeState.REJECTED, identity=identity, reason="not_found")
        if record.expired(now=now):
            record.state = ResumeState.EXPIRED
            return ResumeDecision(False, token, ResumeState.EXPIRED, identity=identity, reason="expired")
        if record.identity != identity:
            record.state = ResumeState.REJECTED
            return ResumeDecision(
                False,
                token,
                ResumeState.REJECTED,
                identity=identity,
                reason="identity_mismatch",
            )
        if (
            not isinstance(requested_offset, int)
            or requested_offset < record.base_offset
            or requested_offset > record.next_offset
        ):
            record.state = ResumeState.REJECTED
            return ResumeDecision(False, token, ResumeState.REJECTED, identity=identity, reason="out_of_window")

        replay_from = requested_offset - record.base_offset
        record.state = ResumeState.RESUMED
        return ResumeDecision(
            True,
            token,
            ResumeState.RESUMED,
            identity=identity,
            accepted_offset=requested_offset,
            replay_units=tuple(record.replay_units[replay_from:]),
        )

    def snapshot(self) -> dict[str, dict[str, Any]]:
        return {token: record.snapshot() for token, record in sorted(self._records.items())}


__all__ = [
    "RESUMABLE_BINDINGS",
    "ResumeDecision",
    "ResumeState",
    "StreamResumeIdentity",
    "StreamResumeRecord",
    "StreamResumeRegistry",
]
