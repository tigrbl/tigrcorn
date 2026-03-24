from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from tigrcorn.asgi.events.http import http_disconnect, http_request, http_request_trailers
from tigrcorn.asgi.events.lifespan import lifespan_shutdown, lifespan_startup
from tigrcorn.errors import ProtocolError
from tigrcorn.protocols.http1.parser import _validate_header_name, _validate_header_value
from tigrcorn.types import Message, StreamReaderLike



FORBIDDEN_REQUEST_TRAILER_NAMES = {
    b'content-length',
    b'transfer-encoding',
    b'host',
    b'trailer',
    b'content-encoding',
    b'content-type',
}


def apply_request_trailer_policy(
    trailers: list[tuple[bytes, bytes]] | tuple[tuple[bytes, bytes], ...],
    policy: str,
) -> list[tuple[bytes, bytes]]:
    normalized = [(bytes(name).lower(), bytes(value)) for name, value in trailers]
    if policy == 'drop':
        return []
    if policy == 'strict':
        forbidden = [name for name, _value in normalized if name in FORBIDDEN_REQUEST_TRAILER_NAMES]
        if forbidden:
            raise ProtocolError(f'forbidden request trailer fields: {forbidden!r}')
    return normalized


class HTTPRequestReceive:
    """Buffered HTTP request body exposed as ASGI receive events."""

    def __init__(self, body: bytes, *, trailers: list[tuple[bytes, bytes]] | None = None, trailer_policy: str = 'pass') -> None:
        self._body = body
        self._trailers = apply_request_trailer_policy(list(trailers or ()), trailer_policy)
        self._sent_body = False
        self._sent_trailers = False

    async def __call__(self) -> Message:
        if not self._sent_body:
            self._sent_body = True
            return http_request(self._body, False)
        if self._trailers and not self._sent_trailers:
            self._sent_trailers = True
            return http_request_trailers(self._trailers)
        return http_disconnect()


class HTTPStreamingRequestReceive:
    """Reader-backed HTTP/1.1 request body exposed incrementally as ASGI events."""

    def __init__(
        self,
        *,
        reader: StreamReaderLike,
        content_length: int | None,
        chunked: bool,
        max_body_size: int,
        expect_continue: bool = False,
        on_expect_continue: Callable[[], Awaitable[None]] | None = None,
        max_chunk_size: int = 65_536,
        trailer_policy: str = 'pass',
    ) -> None:
        if content_length is not None and content_length < 0:
            raise ValueError('content_length must be non-negative')
        self._reader = reader
        self._remaining = content_length
        self._chunked = chunked
        self._max_body_size = max_body_size
        self._max_chunk_size = max_chunk_size
        self._expect_continue = expect_continue
        self._on_expect_continue = on_expect_continue
        self._continue_sent = False
        self._sent_final = False
        self._disconnected = False
        self._total_read = 0
        self.body_complete = not chunked and (content_length is None or content_length == 0)
        self._trailers_sent = False
        self.trailer_policy = trailer_policy
        self.trailers: list[tuple[bytes, bytes]] = []

    async def __call__(self) -> Message:
        if self._disconnected:
            return http_disconnect()
        if self._sent_final:
            if self.trailers and not self._trailers_sent:
                self._trailers_sent = True
                return http_request_trailers(self.trailers)
            self._disconnected = True
            return http_disconnect()
        await self._maybe_send_continue()
        if self._chunked:
            return await self._next_chunked_event()
        if self._remaining is None or self._remaining == 0:
            self.body_complete = True
            self._sent_final = True
            return http_request(b'', False)
        amount = min(self._remaining, self._max_chunk_size)
        data = await self._readexactly(amount)
        self._remaining -= len(data)
        self._total_read += len(data)
        if self._total_read > self._max_body_size:
            raise ProtocolError('request body exceeds configured max_body_size')
        more_body = self._remaining > 0
        if not more_body:
            self.body_complete = True
            self._sent_final = True
        return http_request(data, more_body)

    async def _maybe_send_continue(self) -> None:
        if (
            self._expect_continue
            and not self._continue_sent
            and not self.body_complete
            and self._on_expect_continue is not None
        ):
            self._continue_sent = True
            await self._on_expect_continue()

    async def _read_line(self) -> bytes:
        try:
            return await self._reader.readuntil(b'\r\n')
        except asyncio.IncompleteReadError as exc:
            raise ProtocolError('unexpected EOF while reading HTTP/1.1 body') from exc

    async def _readexactly(self, amount: int) -> bytes:
        try:
            return await self._reader.readexactly(amount)
        except asyncio.IncompleteReadError as exc:
            raise ProtocolError('unexpected EOF while reading HTTP/1.1 body') from exc

    async def _consume_trailers(self) -> None:
        trailers: list[tuple[bytes, bytes]] = []
        while True:
            trailer = await self._read_line()
            if trailer == b'\r\n':
                self.trailers = apply_request_trailer_policy(trailers, self.trailer_policy)
                return
            if trailer[:1] in {b' ', b'\t'}:
                raise ProtocolError('obsolete line folding is not supported')
            if b':' not in trailer[:-2]:
                raise ProtocolError('malformed chunk trailer line')
            name, value = trailer[:-2].split(b':', 1)
            normalized_name = name.strip().lower()
            normalized_value = value.strip()
            _validate_header_name(normalized_name)
            _validate_header_value(normalized_value)
            trailers.append((normalized_name, normalized_value))

    async def _next_chunked_event(self) -> Message:
        line = await self._read_line()
        size_token = line[:-2].split(b';', 1)[0].strip()
        try:
            size = int(size_token, 16)
        except ValueError as exc:
            raise ProtocolError('invalid chunk size') from exc
        if size < 0:
            raise ProtocolError('invalid chunk size')
        if size == 0:
            await self._consume_trailers()
            self.body_complete = True
            self._sent_final = True
            return http_request(b'', False)
        data = await self._readexactly(size)
        terminator = await self._readexactly(2)
        if terminator != b'\r\n':
            raise ProtocolError('invalid chunk terminator')
        self._total_read += size
        if self._total_read > self._max_body_size:
            raise ProtocolError('request body exceeds configured max_body_size')
        return http_request(data, True)


class QueueReceive:
    def __init__(self) -> None:
        self._queue: asyncio.Queue[Message] = asyncio.Queue()

    async def put(self, message: Message) -> None:
        await self._queue.put(message)

    async def __call__(self) -> Message:
        return await self._queue.get()


class LifespanReceive(QueueReceive):
    async def startup(self) -> None:
        await self.put(lifespan_startup())

    async def shutdown(self) -> None:
        await self.put(lifespan_shutdown())
