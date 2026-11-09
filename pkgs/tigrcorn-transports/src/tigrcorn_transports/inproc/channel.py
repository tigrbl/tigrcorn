from __future__ import annotations

import asyncio
from dataclasses import dataclass, field


@dataclass(slots=True)
class InProcChannel:
    capacity: int = 0
    _queue: asyncio.Queue[bytes] = field(init=False)

    def __post_init__(self) -> None:
        self._queue = asyncio.Queue(maxsize=self.capacity)

    async def send(self, payload: bytes) -> None:
        await self._queue.put(payload)

    async def recv(self) -> bytes:
        return await self._queue.get()
