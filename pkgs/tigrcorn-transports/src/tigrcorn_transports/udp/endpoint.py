from __future__ import annotations

import asyncio
from dataclasses import dataclass


@dataclass(slots=True)
class UDPEndpoint:
    transport: asyncio.DatagramTransport
    local_addr: tuple[str, int] | None = None

    def send(self, data: bytes, addr: tuple[str, int]) -> None:
        self.transport.sendto(data, addr)

    def close(self) -> None:
        self.transport.close()
