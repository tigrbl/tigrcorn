from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class LogicalStream:
    stream_id: int
    multiplexed: bool = False
    open: bool = True

    def close(self) -> None:
        self.open = False
