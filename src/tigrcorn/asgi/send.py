from __future__ import annotations

import asyncio
import hashlib
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from tigrcorn.asgi.errors import ASGIProtocolError
from tigrcorn.protocols.content_coding import apply_http_content_coding
from tigrcorn.protocols.http1.serializer import (
    finalize_chunked_body,
    response_allows_body,
    serialize_http11_response_chunk,
    serialize_http11_response_head,
    serialize_http11_response_whole,
)
from tigrcorn.utils.headers import get_header


@dataclass(frozen=True, slots=True)
class MemoryBodySegment:
    data: bytes


@dataclass(frozen=True, slots=True)
class FileBodySegment:
    path: str
    offset: int = 0
    count: int | None = None


BodySegment = MemoryBodySegment | FileBodySegment


DEFAULT_RESPONSE_BODY_SPOOL_THRESHOLD = 256 * 1024


def _format_strong_etag(value: bytes | str) -> bytes:
    if isinstance(value, bytes):
        text = value.decode('latin1')
    else:
        text = value
    opaque = text.replace('\\', '\\\\').replace('"', '\\"').encode('latin1')
    return b'"' + opaque + b'"'


def normalize_response_file_segments(raw_segments: object | None) -> list[BodySegment]:
    segments: list[BodySegment] = []
    for raw in raw_segments or ():
        if isinstance(raw, (MemoryBodySegment, FileBodySegment)):
            segments.append(raw)
            continue
        if isinstance(raw, (bytes, bytearray, memoryview)):
            segments.append(MemoryBodySegment(bytes(raw)))
            continue
        if not isinstance(raw, dict):
            raise ASGIProtocolError(f'invalid tigrcorn.http.response.file segment: {raw!r}')
        segment_type = str(raw.get('type', 'file')).lower()
        if segment_type == 'memory':
            segments.append(MemoryBodySegment(bytes(raw.get('body', b''))))
            continue
        if segment_type != 'file':
            raise ASGIProtocolError(f'unsupported tigrcorn.http.response.file segment type: {segment_type!r}')
        count_raw = raw.get('count')
        segments.append(
            FileBodySegment(
                path=os.fspath(raw['path']),
                offset=int(raw.get('offset', 0)),
                count=None if count_raw is None else int(count_raw),
            )
        )
    return segments


def normalize_response_pathsend_segment(raw_path: object) -> FileBodySegment:
    path = os.fspath(raw_path)
    if not os.path.isabs(path):
        raise ASGIProtocolError('http.response.pathsend requires an absolute file path')
    return FileBodySegment(path, 0, None)


async def _iter_file_segment_bytes(segment: FileBodySegment, *, chunk_size: int = 64 * 1024):
    path = os.fspath(segment.path)
    remaining = segment.count
    position = segment.offset
    if remaining is not None and remaining <= 0:
        return
    if hasattr(os, 'pread'):
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
        with open(path, 'rb') as handle:
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
        async for chunk in _iter_file_segment_bytes(segment, chunk_size=chunk_size):
            yield chunk


async def materialize_response_body_segments(
    segments: list[BodySegment] | tuple[BodySegment, ...],
    *,
    chunk_size: int = 64 * 1024,
) -> bytes:
    chunks: list[bytes] = []
    async for chunk in iter_response_body_segments(segments, chunk_size=chunk_size):
        chunks.append(chunk)
    return b''.join(chunks)


def _segment_length(segment: BodySegment) -> int:
    if isinstance(segment, MemoryBodySegment):
        return len(segment.data)
    if segment.count is not None:
        return max(int(segment.count), 0)
    try:
        size = Path(segment.path).stat().st_size
    except FileNotFoundError:
        return 0
    return max(size - int(segment.offset), 0)


def response_body_segments_have_bytes(segments: list[BodySegment] | tuple[BodySegment, ...]) -> bool:
    return any(_segment_length(segment) > 0 for segment in segments)


@dataclass(slots=True)
class HTTPResponseCollector:
    status: int | None = None
    headers: list[tuple[bytes, bytes]] = field(default_factory=list)
    body_parts: list[bytes] = field(default_factory=list)
    trailers: list[tuple[bytes, bytes]] = field(default_factory=list)
    complete: bool = False
    informational_responses: list[tuple[int, list[tuple[bytes, bytes]]]] = field(default_factory=list)
    body_segments: list[BodySegment] = field(default_factory=list)
    uses_streamed_body: bool = False
    spool_threshold: int = field(default_factory=lambda: DEFAULT_RESPONSE_BODY_SPOOL_THRESHOLD)
    body_length: int = 0
    _body_digest: object = field(default_factory=lambda: hashlib.blake2s(digest_size=16), repr=False)
    _spool_path: str | None = field(default=None, init=False, repr=False)
    _spool_handle: object | None = field(default=None, init=False, repr=False)
    _body_channel: str | None = field(default=None, init=False, repr=False)

    def _record_body_chunk(self, chunk: bytes) -> None:
        if not chunk:
            return
        self.body_length += len(chunk)
        self._body_digest.update(chunk)

    def has_spooled_body(self) -> bool:
        return self._spool_path is not None

    def generated_entity_tag(self) -> bytes:
        return _format_strong_etag(self._body_digest.hexdigest().encode('ascii'))

    def _ensure_spool_file(self) -> None:
        if self._spool_handle is not None and self._spool_path is not None:
            return
        handle = tempfile.NamedTemporaryFile(prefix='tigrcorn-response-', suffix='.bin', delete=False)
        self._spool_handle = handle
        self._spool_path = handle.name
        if self.body_parts:
            for part in self.body_parts:
                if part:
                    handle.write(part)
            handle.flush()
            self.body_parts.clear()

    def _flush_spool(self) -> None:
        handle = self._spool_handle
        if handle is not None:
            handle.flush()

    def spooled_body_segments(self) -> list[BodySegment]:
        if self._spool_path is None:
            return []
        self._flush_spool()
        return [FileBodySegment(self._spool_path, 0, self.body_length)]

    async def materialize_body(self) -> bytes:
        self.finalize()
        if self._spool_path is None:
            return b''.join(self.body_parts)
        return await materialize_response_body_segments(self.spooled_body_segments())

    def cleanup(self) -> None:
        handle = self._spool_handle
        self._spool_handle = None
        if handle is not None:
            try:
                handle.close()
            except Exception:
                pass
        path = self._spool_path
        self._spool_path = None
        if path:
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass

    async def __call__(self, message: dict) -> None:
        message_type = message["type"]
        if message_type == "http.response.start":
            status = int(message["status"])
            headers = list(message.get("headers", []))
            if status < 200:
                if self.status is not None or self.body_parts or self.complete or self.uses_streamed_body or self.has_spooled_body():
                    raise ASGIProtocolError("informational response sent after final response start")
                self.informational_responses.append((status, headers))
                return
            if self.status is not None:
                raise ASGIProtocolError("http.response.start sent more than once")
            self.status = status
            self.headers = headers
            return

        if message_type == "http.response.body":
            if self.status is None:
                raise ASGIProtocolError("http.response.body sent before final http.response.start")
            if self._body_channel in {'file', 'pathsend'}:
                raise ASGIProtocolError('http.response.body cannot follow streamed file response')
            self._body_channel = 'body'
            chunk = bytes(message.get("body", b""))
            self._record_body_chunk(chunk)
            should_spool = self.has_spooled_body() or (self.spool_threshold > 0 and self.body_length > self.spool_threshold)
            if should_spool:
                self._ensure_spool_file()
                if chunk:
                    assert self._spool_handle is not None
                    self._spool_handle.write(chunk)
            else:
                self.body_parts.append(chunk)
            self.complete = not bool(message.get("more_body", False))
            return

        if message_type == 'tigrcorn.http.response.file':
            if self.status is None:
                raise ASGIProtocolError('tigrcorn.http.response.file sent before final http.response.start')
            if self.body_parts or self.has_spooled_body() or self._body_channel == 'body':
                raise ASGIProtocolError('tigrcorn.http.response.file cannot follow buffered body events')
            if self._body_channel == 'pathsend':
                raise ASGIProtocolError('tigrcorn.http.response.file cannot follow http.response.pathsend')
            self._body_channel = 'file'
            self.uses_streamed_body = True
            self.body_segments.extend(normalize_response_file_segments(message.get('segments')))
            self.complete = not bool(message.get('more_body', False))
            return

        if message_type == 'http.response.pathsend':
            if self.status is None:
                raise ASGIProtocolError('http.response.pathsend sent before final http.response.start')
            if self.body_parts or self.has_spooled_body() or self._body_channel is not None:
                raise ASGIProtocolError('http.response.pathsend cannot be mixed with buffered or streamed body events')
            if bool(message.get('more_body', False)):
                raise ASGIProtocolError('http.response.pathsend does not support more_body')
            self._body_channel = 'pathsend'
            self.uses_streamed_body = True
            self.body_segments.append(normalize_response_pathsend_segment(message.get('path')))
            self.complete = True
            return

        if message_type == "http.response.trailers":
            if self.status is None:
                raise ASGIProtocolError("http.response.trailers sent before final http.response.start")
            self.trailers.extend(list(message.get("trailers", [])))
            self.complete = not bool(message.get("more_trailers", False))
            return

        raise ASGIProtocolError(f"unexpected HTTP send event: {message_type!r}")

    def finalize(self) -> None:
        if self.status is None:
            raise ASGIProtocolError("application did not send final http.response.start")
        if not self.complete:
            raise ASGIProtocolError("application returned before completing the response body")
        self._flush_spool()

    def response_tuple(self) -> tuple[int, list[tuple[bytes, bytes]], bytes, list[tuple[bytes, bytes]]]:
        self.finalize()
        assert self.status is not None
        if self._spool_path is None:
            body = b''.join(self.body_parts)
        else:
            with open(self._spool_path, 'rb') as handle:
                body = handle.read()
        return self.status, self.headers, body, list(self.trailers)


class HTTPResponseWriter:
    def __init__(
        self,
        writer: asyncio.StreamWriter,
        *,
        keep_alive: bool,
        server_header: bytes | None,
        method: str,
        request_headers: list[tuple[bytes, bytes]] | tuple[tuple[bytes, bytes], ...] = (),
        content_coding_policy: str = 'allowlist',
        content_codings: tuple[str, ...] = ('br', 'gzip', 'deflate'),
        include_date_header: bool = True,
        default_headers: list[tuple[bytes, bytes]] | tuple[tuple[bytes, bytes], ...] = (),
    ) -> None:
        self.writer = writer
        self.keep_alive = keep_alive
        self.server_header = server_header
        self.method = method.upper()
        self.request_headers = list(request_headers)
        self.content_coding_policy = content_coding_policy
        self.content_codings = tuple(content_codings)
        self.include_date_header = include_date_header
        self.default_headers = list(default_headers)
        self.status: int | None = None
        self.headers: list[tuple[bytes, bytes]] = []
        self.started = False
        self.finished = False
        self.chunked = False
        self.head_only = self.method == "HEAD"
        self.informational_sent = False
        self._buffered_body_parts: list[bytes] = []
        self._buffering_for_content_coding = False
        self._response_trailers: list[tuple[bytes, bytes]] = []
        self._body_channel: str | None = None

    async def __call__(self, message: dict) -> None:
        typ = message["type"]
        if typ == "http.response.start":
            await self._handle_response_start(message)
            return
        if typ == "http.response.trailers":
            await self._handle_response_trailers(message)
            return
        if typ == 'tigrcorn.http.response.file':
            await self._handle_response_file(message)
            return
        if typ == 'http.response.pathsend':
            await self._handle_response_pathsend(message)
            return
        if typ != "http.response.body":
            raise ASGIProtocolError(f"unexpected HTTP send event: {typ!r}")
        await self._handle_response_body(message)

    async def _handle_response_start(self, message: dict) -> None:
        status = int(message["status"])
        headers = list(message.get("headers", []))
        if status < 200:
            if self.status is not None or self.started or self.finished:
                raise ASGIProtocolError("informational response sent after final response start")
            raw = serialize_http11_response_head(
                status=status,
                headers=headers,
                keep_alive=self.keep_alive,
                server_header=self.server_header,
                chunked=False,
                include_date_header=self.include_date_header,
                default_headers=self.default_headers,
            )
            self.writer.write(raw)
            await self.writer.drain()
            self.informational_sent = True
            return
        if self.status is not None:
            raise ASGIProtocolError("http.response.start sent more than once")
        self.status = status
        self.headers = headers

    def _should_buffer_for_content_coding(self) -> bool:
        if self.status is None or not response_allows_body(self.status):
            return False
        if get_header(self.request_headers, b'accept-encoding') is None:
            return False
        if get_header(self.headers, b'content-encoding') is not None:
            return False
        return True

    async def _flush_buffered_response(self) -> None:
        assert self.status is not None
        status, headers, payload, _selection = apply_http_content_coding(
            request_headers=self.request_headers,
            response_headers=self.headers,
            body=b''.join(self._buffered_body_parts),
            status=self.status,
            policy=self.content_coding_policy,
            supported=self.content_codings,
        )
        self.status = status
        self.headers = headers
        if self.head_only and response_allows_body(status):
            raw = serialize_http11_response_head(
                status=status,
                headers=headers,
                keep_alive=self.keep_alive,
                server_header=self.server_header,
                chunked=False,
                include_date_header=self.include_date_header,
                default_headers=self.default_headers,
            )
        else:
            raw = serialize_http11_response_whole(
                status=status,
                headers=headers,
                body=payload if response_allows_body(status) and not self.head_only else b'',
                keep_alive=self.keep_alive,
                server_header=self.server_header,
                include_date_header=self.include_date_header,
                default_headers=self.default_headers,
            )
        self.writer.write(raw)
        await self.writer.drain()
        self.started = True
        self.finished = True

    async def _handle_response_body(self, message: dict) -> None:
        if self.status is None:
            raise ASGIProtocolError("http.response.body sent before final http.response.start")
        if self._body_channel in {'file', 'pathsend'}:
            raise ASGIProtocolError('http.response.body cannot follow streamed file response')
        self._body_channel = 'body'

        body = message.get("body", b"")
        more_body = bool(message.get("more_body", False))
        status_allows_body = response_allows_body(self.status)
        body_allowed = status_allows_body and not self.head_only

        if self._should_buffer_for_content_coding():
            self._buffering_for_content_coding = True
            self._buffered_body_parts.append(body)
            if not more_body:
                await self._flush_buffered_response()
            return

        if not self.started:
            has_len = get_header(self.headers, b"content-length") is not None
            self.chunked = body_allowed and not has_len and more_body
            if not more_body and not has_len:
                if self.head_only and status_allows_body:
                    head_headers = list(self.headers)
                    head_headers.append((b"content-length", str(len(body)).encode("ascii")))
                    raw = serialize_http11_response_head(
                        status=self.status,
                        headers=head_headers,
                        keep_alive=self.keep_alive,
                        server_header=self.server_header,
                        chunked=False,
                        include_date_header=self.include_date_header,
                        default_headers=self.default_headers,
                    )
                else:
                    payload = body if body_allowed else b""
                    raw = serialize_http11_response_whole(
                        status=self.status,
                        headers=self.headers,
                        body=payload,
                        keep_alive=self.keep_alive,
                        server_header=self.server_header,
                        include_date_header=self.include_date_header,
                        default_headers=self.default_headers,
                    )
                self.writer.write(raw)
                await self.writer.drain()
                self.started = True
                self.finished = True
                return

            raw_head = serialize_http11_response_head(
                status=self.status,
                headers=self.headers,
                keep_alive=self.keep_alive,
                server_header=self.server_header,
                chunked=self.chunked,
                include_date_header=self.include_date_header,
                default_headers=self.default_headers,
            )
            self.writer.write(raw_head)
            self.started = True
            if body and body_allowed:
                if self.chunked:
                    self.writer.write(serialize_http11_response_chunk(body))
                else:
                    self.writer.write(body)
            if not more_body:
                if self.chunked:
                    self.writer.write(finalize_chunked_body())
                self.finished = True
            await self.writer.drain()
            return

        if self.finished:
            raise ASGIProtocolError("response body sent after response completion")
        if body and body_allowed:
            if self.chunked:
                self.writer.write(serialize_http11_response_chunk(body))
            else:
                self.writer.write(body)
        if not more_body:
            if self.chunked:
                self.writer.write(finalize_chunked_body())
            self.finished = True
        await self.writer.drain()

    async def _handle_response_file(self, message: dict, *, from_pathsend: bool = False) -> None:
        if self.status is None:
            raise ASGIProtocolError('tigrcorn.http.response.file sent before final http.response.start')
        if self._body_channel == 'body':
            raise ASGIProtocolError('tigrcorn.http.response.file cannot follow buffered body events')
        if self._body_channel == 'pathsend' and not from_pathsend:
            raise ASGIProtocolError('tigrcorn.http.response.file cannot follow http.response.pathsend')
        if from_pathsend:
            if self._body_channel is not None:
                raise ASGIProtocolError('http.response.pathsend cannot be mixed with buffered or streamed body events')
            self._body_channel = 'pathsend'
        else:
            if self._body_channel is None:
                self._body_channel = 'file'
        if self.finished:
            raise ASGIProtocolError('response body sent after response completion')
        segments = normalize_response_file_segments(message.get('segments'))
        more_body = bool(message.get('more_body', False))
        if from_pathsend and more_body:
            raise ASGIProtocolError('http.response.pathsend does not support more_body')
        has_len = get_header(self.headers, b'content-length') is not None
        status_allows_body = response_allows_body(self.status)
        body_allowed = status_allows_body and not self.head_only
        if not self.started:
            self.chunked = body_allowed and not has_len and (response_body_segments_have_bytes(segments) or more_body)
            raw_head = serialize_http11_response_head(
                status=self.status,
                headers=self.headers,
                keep_alive=self.keep_alive,
                server_header=self.server_header,
                chunked=self.chunked,
                include_date_header=self.include_date_header,
                default_headers=self.default_headers,
            )
            self.writer.write(raw_head)
            await self.writer.drain()
            self.started = True
        if body_allowed:
            async for chunk in iter_response_body_segments(segments):
                if self.chunked:
                    self.writer.write(serialize_http11_response_chunk(chunk))
                else:
                    self.writer.write(chunk)
                await self.writer.drain()
        if not more_body:
            if self.chunked:
                self.writer.write(finalize_chunked_body())
                await self.writer.drain()
            self.finished = True

    async def _handle_response_pathsend(self, message: dict) -> None:
        segment = normalize_response_pathsend_segment(message.get('path'))
        await self._handle_response_file(
            {
                'type': 'tigrcorn.http.response.file',
                'segments': [segment],
                'more_body': False,
            },
            from_pathsend=True,
        )

    async def _handle_response_trailers(self, message: dict) -> None:
        if self.status is None:
            raise ASGIProtocolError("http.response.trailers sent before final http.response.start")
        trailers = [(bytes(name).lower(), bytes(value)) for name, value in message.get("trailers", [])]
        if not self.started:
            raw_head = serialize_http11_response_head(
                status=self.status,
                headers=self.headers,
                keep_alive=self.keep_alive,
                server_header=self.server_header,
                chunked=True,
                include_date_header=self.include_date_header,
                default_headers=self.default_headers,
            )
            self.writer.write(raw_head)
            self.started = True
            self.chunked = True
        if self.finished:
            raise ASGIProtocolError("response trailers sent after response completion")
        self._response_trailers.extend(trailers)
        if self.chunked:
            self.writer.write(finalize_chunked_body(trailers))
            await self.writer.drain()
        self.finished = not bool(message.get("more_trailers", False))

    async def ensure_complete(self) -> None:
        if self.status is None:
            raise ASGIProtocolError("application did not send final http.response.start")
        if self._buffering_for_content_coding and not self.finished:
            await self._flush_buffered_response()
            return
        if not self.started:
            raw = serialize_http11_response_whole(
                status=self.status,
                headers=self.headers,
                body=b"",
                keep_alive=self.keep_alive,
                server_header=self.server_header,
                include_date_header=self.include_date_header,
                default_headers=self.default_headers,
            )
            self.writer.write(raw)
            await self.writer.drain()
            self.started = True
            self.finished = True
            return
        if not self.finished:
            if self.chunked:
                self.writer.write(finalize_chunked_body())
                await self.writer.drain()
            self.finished = True


class LifespanSend:
    def __init__(self) -> None:
        self._queue: asyncio.Queue[dict] = asyncio.Queue()

    async def __call__(self, message: dict) -> None:
        await self._queue.put(message)

    async def get(self) -> dict:
        return await self._queue.get()
