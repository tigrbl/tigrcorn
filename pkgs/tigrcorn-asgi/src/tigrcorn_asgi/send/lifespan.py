from __future__ import annotations

import asyncio


class LifespanSend:
    def __init__(self) -> None:
        self._queue: asyncio.Queue[dict] = asyncio.Queue()

    async def __call__(self, message: dict) -> None:
        await self._queue.put(message)

    async def get(self) -> dict:
        return await self._queue.get()
