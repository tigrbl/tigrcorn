from __future__ import annotations

from dataclasses import dataclass, field
from time import monotonic
from typing import Any, Callable


@dataclass(slots=True)
class LocalWorker:
    name: str = 'local'
    running: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    start_count: int = 0
    stop_count: int = 0
    last_started_at: float | None = None
    callback: Callable[[], None] | None = None

    def start(self) -> None:
        self.running = True
        self.start_count += 1
        self.last_started_at = monotonic()
        if self.callback is not None:
            self.callback()

    def stop(self) -> None:
        self.running = False
        self.stop_count += 1

    def health(self) -> dict[str, Any]:
        return {
            'name': self.name,
            'alive': self.running,
            'start_count': self.start_count,
            'stop_count': self.stop_count,
            'last_started_at': self.last_started_at,
        }
