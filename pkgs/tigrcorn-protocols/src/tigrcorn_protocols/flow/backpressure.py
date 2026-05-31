from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class BackpressureState:
    paused: bool = False
    high_water: int = 64 * 1024
    low_water: int = 16 * 1024

    def update(self, buffered: int) -> bool:
        if buffered >= self.high_water:
            self.paused = True
        elif buffered <= self.low_water:
            self.paused = False
        return self.paused
