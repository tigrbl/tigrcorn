from __future__ import annotations

from dataclasses import dataclass, field
from time import monotonic


@dataclass(slots=True)
class BaseSession:
    session_id: int
    opened_at: float = field(default_factory=monotonic)
    protocol: str = 'unknown'
    closed_at: float | None = None

    def close(self) -> None:
        if self.closed_at is None:
            self.closed_at = monotonic()
