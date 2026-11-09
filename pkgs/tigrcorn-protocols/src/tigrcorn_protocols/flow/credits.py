from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class CreditWindow:
    remaining: int

    def consume(self, n: int) -> None:
        if n < 0:
            raise ValueError('credit consumption must be non-negative')
        self.remaining = max(0, self.remaining - n)

    def refill(self, n: int) -> None:
        if n < 0:
            raise ValueError('credit refill must be non-negative')
        self.remaining += n

    def available(self, n: int = 1) -> bool:
        return self.remaining >= n
