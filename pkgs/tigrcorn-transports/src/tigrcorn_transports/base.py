from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class TransportDescriptor:
    name: str
    multiplexed: bool = False
