from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SessionLimits:
    max_streams: int = 128
    max_inflight_bytes: int = 1_048_576

    def allow_stream(self, current: int) -> bool:
        return current < self.max_streams
