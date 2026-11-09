from __future__ import annotations

import asyncio


async def accept(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    return reader, writer
