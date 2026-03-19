from __future__ import annotations

from dataclasses import dataclass
from time import monotonic


@dataclass(slots=True)
class KeepAlivePolicy:
    idle_timeout: float = 30.0
    ping_interval: float = 15.0

    def expired(self, last_activity: float, now: float | None = None) -> bool:
        now = monotonic() if now is None else now
        return now - last_activity >= self.idle_timeout

    def should_ping(self, last_activity: float, now: float | None = None) -> bool:
        now = monotonic() if now is None else now
        return now - last_activity >= self.ping_interval
