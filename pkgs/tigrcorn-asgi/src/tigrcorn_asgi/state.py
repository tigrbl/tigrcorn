from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ConnectionState:
    started: bool = False
    closed: bool = False
