from __future__ import annotations

from dataclasses import dataclass, field
from time import monotonic


@dataclass(slots=True)
class UDPPacket:
    data: bytes
    addr: tuple[str, int]
    received_at: float = field(default_factory=monotonic)

    def __len__(self) -> int:
        return len(self.data)
