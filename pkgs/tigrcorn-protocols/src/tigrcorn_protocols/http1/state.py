from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class HTTP11ConnectionState:
    requests_served: int = 0
    keep_alive: bool = True
