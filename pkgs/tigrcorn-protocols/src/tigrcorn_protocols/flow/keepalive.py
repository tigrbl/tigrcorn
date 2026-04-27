from __future__ import annotations

from dataclasses import dataclass, field
from time import monotonic


@dataclass(slots=True)
class KeepAlivePolicy:
    idle_timeout: float = 30.0
    ping_interval: float | None = None
    ping_timeout: float | None = None

    @property
    def effective_ping_interval(self) -> float | None:
        if self.ping_interval is not None:
            return self.ping_interval
        return self.ping_timeout

    @property
    def effective_ping_timeout(self) -> float | None:
        interval = self.effective_ping_interval
        if self.ping_timeout is not None:
            return self.ping_timeout
        return interval

    def expired(self, last_activity: float, now: float | None = None) -> bool:
        now = monotonic() if now is None else now
        return now - last_activity >= self.idle_timeout

    def should_ping(self, last_activity: float, now: float | None = None) -> bool:
        interval = self.effective_ping_interval
        if interval is None:
            return False
        now = monotonic() if now is None else now
        return now - last_activity >= interval

    def ping_timed_out(self, ping_sent_at: float, now: float | None = None) -> bool:
        timeout = self.effective_ping_timeout
        if timeout is None:
            return False
        now = monotonic() if now is None else now
        return now - ping_sent_at >= timeout

    @property
    def enabled(self) -> bool:
        return self.effective_ping_interval is not None


@dataclass(slots=True)
class KeepAliveRuntime:
    policy: KeepAlivePolicy
    last_activity: float = field(default_factory=monotonic)
    pending_ping_payload: bytes | None = None
    pending_ping_sent_at: float | None = None
    sequence: int = 0

    def record_activity(self, now: float | None = None) -> None:
        self.last_activity = monotonic() if now is None else now

    def next_ping_payload(self, now: float | None = None) -> bytes | None:
        if self.pending_ping_payload is not None:
            return None
        if not self.policy.should_ping(self.last_activity, now=now):
            return None
        self.sequence += 1
        payload = self.sequence.to_bytes(8, 'big')
        self.pending_ping_payload = payload
        self.pending_ping_sent_at = monotonic() if now is None else now
        return payload

    def acknowledge_pong(self, payload: bytes, now: float | None = None) -> bool:
        if self.pending_ping_payload is None:
            self.record_activity(now=now)
            return False
        if payload and payload != self.pending_ping_payload:
            return False
        self.pending_ping_payload = None
        self.pending_ping_sent_at = None
        self.record_activity(now=now)
        return True

    def ping_timed_out(self, now: float | None = None) -> bool:
        if self.pending_ping_sent_at is None:
            return False
        return self.policy.ping_timed_out(self.pending_ping_sent_at, now=now)
