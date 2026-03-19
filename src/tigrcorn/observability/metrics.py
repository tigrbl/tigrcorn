from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Metrics:
    connections_opened: int = 0
    connections_closed: int = 0
    requests_served: int = 0
    websocket_connections: int = 0
