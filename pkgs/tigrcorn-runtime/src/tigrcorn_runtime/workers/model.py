from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class WorkerConfig:
    processes: int = 1
    graceful_shutdown_timeout: float = 30.0
