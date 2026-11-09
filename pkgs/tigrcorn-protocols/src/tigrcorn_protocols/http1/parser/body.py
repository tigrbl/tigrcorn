from __future__ import annotations

import asyncio

from tigrcorn_core.errors import ProtocolError
from tigrcorn_core.types import StreamReaderLike

from .validation import _validate_header_name, _validate_header_value


async def _read_line(reader: StreamReaderLike) -> bytes:
    try:
        return await reader.readuntil(b"\r\n")
    except asyncio.IncompleteReadError as exc:
        raise ProtocolError('unexpected EOF while reading HTTP/1.1 body') from exc


async def _readexactly(reader: StreamReaderLike, amount: int) -> bytes:
    try:
        return await reader.readexactly(amount)
    except asyncio.IncompleteReadError as exc:
        raise ProtocolError('unexpected EOF while reading HTTP/1.1 body') from exc


async def _read_request_head_until_terminator(
    reader: StreamReaderLike,
    *,
    limit: int,
    buffer_size: int,
) -> bytes:
    limited_readuntil = getattr(reader, 'readuntil_limited', None)
    if callable(limited_readuntil):
        try:
            return await limited_readuntil(b"\r\n\r\n", limit=limit, read_chunk_size=buffer_size)
        except TypeError:
            return await limited_readuntil(b"\r\n\r\n", limit=limit)
    head = await reader.readuntil(b"\r\n\r\n")
    if len(head) > limit:
        raise asyncio.LimitOverrunError('request head exceeds configured HTTP/1.1 request-head limit', consumed=len(head))
    return head


async def _consume_chunked_trailers(reader: StreamReaderLike) -> None:
    while True:
        trailer = await _read_line(reader)
        if trailer == b"\r\n":
            return
        if trailer[:1] in {b' ', b'\t'}:
            raise ProtocolError('obsolete line folding is not supported')
        if b':' not in trailer[:-2]:
            raise ProtocolError('malformed chunk trailer line')
        name, value = trailer[:-2].split(b':', 1)
        _validate_header_name(name.strip().lower())
        _validate_header_value(value.strip())


async def _read_chunked_body(reader: StreamReaderLike, *, max_body_size: int) -> bytes:
    parts: list[bytes] = []
    total = 0
    while True:
        line = await _read_line(reader)
        size_token = line[:-2].split(b';', 1)[0].strip()
        try:
            size = int(size_token, 16)
        except ValueError as exc:
            raise ProtocolError('invalid chunk size') from exc
        if size < 0:
            raise ProtocolError('invalid chunk size')
        if size == 0:
            await _consume_chunked_trailers(reader)
            return b''.join(parts)
        chunk = await _readexactly(reader, size)
        terminator = await _readexactly(reader, 2)
        if terminator != b"\r\n":
            raise ProtocolError('invalid chunk terminator')
        total += size
        if total > max_body_size:
            raise ProtocolError('request body exceeds configured max_body_size')
        parts.append(chunk)
