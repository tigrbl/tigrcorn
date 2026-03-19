from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class LocalWorker:
    name: str = 'local'
    running: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def start(self) -> None:
        self.running = True

    def stop(self) -> None:
        self.running = False
