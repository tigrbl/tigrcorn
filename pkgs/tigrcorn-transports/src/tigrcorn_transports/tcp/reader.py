from __future__ import annotations

import asyncio


class PrebufferedReader:
    """A small adapter that serves an initial byte prefix before the underlying reader."""

    def __init__(self, reader: asyncio.StreamReader, initial: bytes = b"") -> None:
        self._reader = reader
        self._buffer = bytearray(initial)

    async def read(self, n: int = -1) -> bytes:
        if n == -1:
            if self._buffer:
                data = bytes(self._buffer)
                self._buffer.clear()
                rest = await self._reader.read(-1)
                return data + rest
            return await self._reader.read(-1)
        if self._buffer:
            take = min(n, len(self._buffer))
            data = bytes(self._buffer[:take])
            del self._buffer[:take]
            if take == n:
                return data
            return data + await self._reader.read(n - take)
        return await self._reader.read(n)

    async def readexactly(self, n: int) -> bytes:
        if len(self._buffer) >= n:
            data = bytes(self._buffer[:n])
            del self._buffer[:n]
            return data
        prefix = bytes(self._buffer)
        self._buffer.clear()
        return prefix + await self._reader.readexactly(n - len(prefix))

    async def readuntil(self, separator: bytes = b"\n") -> bytes:
        return await self.readuntil_limited(separator, limit=None)

    async def readuntil_limited(self, separator: bytes = b"\n", *, limit: int | None, read_chunk_size: int = 65536) -> bytes:
        if not separator:
            raise ValueError("separator must not be empty")
        while True:
            idx = self._buffer.find(separator)
            if idx != -1:
                end = idx + len(separator)
                data = bytes(self._buffer[:end])
                del self._buffer[:end]
                return data
            if limit is not None and len(self._buffer) > limit:
                raise asyncio.LimitOverrunError("separator is not found, and chunk exceed the limit", consumed=len(self._buffer))
            chunk = await self._reader.read(max(1, read_chunk_size))
            if not chunk:
                raise asyncio.IncompleteReadError(partial=bytes(self._buffer), expected=None)
            self._buffer.extend(chunk)
            if limit is not None and len(self._buffer) > limit:
                raise asyncio.LimitOverrunError("separator is not found, and chunk exceed the limit", consumed=len(self._buffer))
