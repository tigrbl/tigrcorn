from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class RawFramedState:
    frames_received: int = 0
    frames_sent: int = 0
