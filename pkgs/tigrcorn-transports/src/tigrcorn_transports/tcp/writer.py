from __future__ import annotations

import asyncio


async def write_all(writer: asyncio.StreamWriter, data: bytes) -> None:
    writer.write(data)
    await writer.drain()
