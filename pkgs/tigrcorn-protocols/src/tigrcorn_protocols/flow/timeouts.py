from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class TimeoutPolicy:
    read_timeout: float = 30.0
    write_timeout: float = 30.0

    async def wait_read(self, awaitable):
        return await asyncio.wait_for(awaitable, timeout=self.read_timeout)

    async def wait_write(self, awaitable):
        return await asyncio.wait_for(awaitable, timeout=self.write_timeout)
