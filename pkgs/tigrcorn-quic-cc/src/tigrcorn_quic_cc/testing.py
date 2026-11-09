from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .api import CongestionController
from .models import SendLimits
from .validation import validate_send_limits


@dataclass(slots=True)
class DeterministicClock:
    value: float = 0.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> float:
        if seconds < 0:
            raise ValueError("clock cannot move backwards")
        self.value += seconds
        return self.value


def collect_send_limits(
    controller: CongestionController,
    timestamps: Iterable[float],
    *,
    max_datagram_size: int,
) -> tuple[SendLimits, ...]:
    return tuple(
        validate_send_limits(
            controller.send_limits(timestamp),
            max_datagram_size=max_datagram_size,
        )
        for timestamp in timestamps
    )
