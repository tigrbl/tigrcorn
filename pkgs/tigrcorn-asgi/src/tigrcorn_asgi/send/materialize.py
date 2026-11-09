from __future__ import annotations

import asyncio
import os

from .segments import BodySegment, FileBodySegment, MemoryBodySegment


async def iter_file_segment_bytes(segment: FileBodySegment, *, chunk_size: int = 64 * 1024):
    path = os.fspath(segment.path)
    remaining = segment.count
    position = segment.offset
    if remaining is not None and remaining <= 0:
        return
    if hasattr(os, "pread"):
        fd = os.open(path, os.O_RDONLY)
        try:
            while remaining is None or remaining > 0:
                size = chunk_size if remaining is None else min(chunk_size, remaining)
                if size <= 0:
                    break
                chunk = await asyncio.to_thread(os.pread, fd, size, position)
                if not chunk:
                    break
                position += len(chunk)
                if remaining is not None:
                    remaining -= len(chunk)
                yield chunk
        finally:
            os.close(fd)
        return

    def _read_chunk(current: int, size: int) -> bytes:
        with open(path, "rb") as handle:
            handle.seek(current)
            return handle.read(size)

    while remaining is None or remaining > 0:
        size = chunk_size if remaining is None else min(chunk_size, remaining)
        if size <= 0:
            break
        chunk = await asyncio.to_thread(_read_chunk, position, size)
        if not chunk:
            break
        position += len(chunk)
        if remaining is not None:
            remaining -= len(chunk)
        yield chunk


async def iter_response_body_segments(
    segments: list[BodySegment] | tuple[BodySegment, ...],
    *,
    chunk_size: int = 64 * 1024,
):
    for segment in segments:
        if isinstance(segment, MemoryBodySegment):
            if segment.data:
                yield bytes(segment.data)
            continue
        async for chunk in iter_file_segment_bytes(segment, chunk_size=chunk_size):
            yield chunk


async def materialize_response_body_segments(
    segments: list[BodySegment] | tuple[BodySegment, ...],
    *,
    chunk_size: int = 64 * 1024,
) -> bytes:
    chunks: list[bytes] = []
    async for chunk in iter_response_body_segments(segments, chunk_size=chunk_size):
        chunks.append(chunk)
    return b"".join(chunks)
