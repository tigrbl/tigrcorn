from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Event:
    name: str
    attrs: dict[str, object]
