from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SchedulerPolicy:
    max_connections: int = 10_000
    max_tasks: int = 50_000
    max_streams_per_session: int = 128
    limit_concurrency: int | None = None
    drain_on_shutdown: bool = True
