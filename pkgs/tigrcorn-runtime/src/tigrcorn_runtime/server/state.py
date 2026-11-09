from __future__ import annotations

from dataclasses import dataclass, field
from time import monotonic

from tigrcorn_observability.metrics import Metrics


@dataclass(slots=True)
class ServerState:
    started_at: float = field(default_factory=monotonic)
    metrics: Metrics = field(default_factory=Metrics)
    shutting_down: bool = False
