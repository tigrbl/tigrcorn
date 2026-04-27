from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Watermarks:
    low: int = 16 * 1024
    high: int = 64 * 1024

    def classify(self, value: int) -> str:
        if value >= self.high:
            return 'high'
        if value <= self.low:
            return 'low'
        return 'mid'
