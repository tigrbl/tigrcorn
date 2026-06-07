from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SchedulerConfig:
    limit_concurrency: int | None = None
    max_connections: int | None = None
    max_tasks: int | None = None
    max_streams: int | None = None
