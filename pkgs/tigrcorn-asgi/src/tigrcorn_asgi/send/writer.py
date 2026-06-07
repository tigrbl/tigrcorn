from __future__ import annotations

import asyncio

from tigrcorn_asgi.errors import ASGIProtocolError
from tigrcorn_core.utils.headers import get_header
from tigrcorn_protocols.content_coding import apply_http_content_coding
from tigrcorn_protocols.http1.serializer import (
    finalize_chunked_body,
    response_allows_body,
    serialize_http11_response_chunk,
    serialize_http11_response_head,
    serialize_http11_response_whole,
)

from .helpers import response_body_segments_have_bytes
from .materialize import iter_response_body_segments
from .validation import normalize_response_file_segments, normalize_response_pathsend_segment


class HTTPResponseWriter:
    def __init__(
        self,
        writer: asyncio.StreamWriter,
        *,
        keep_alive: bool,
        server_header: bytes | None,
        method: str,
        request_headers: list[tuple[bytes, bytes]] | tuple[tuple[bytes, bytes], ...] = (),
        content_coding_policy: str = "allowlist",
        content_codings: tuple[str, ...] = ("br", "gzip", "deflate"),
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
        if typ == "tigrcorn.http.response.file":
            await self._handle_response_file(message)
            return
        if typ == "http.response.pathsend":
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
        if get_header(self.request_headers, b"accept-encoding") is None:
            return False
        if get_header(self.headers, b"content-encoding") is not None:
            return False
        return True

    async def _flush_buffered_response(self) -> None:
        assert self.status is not None
        status, headers, payload, _selection = apply_http_content_coding(
            request_headers=self.request_headers,
            response_headers=self.headers,
            body=b"".join(self._buffered_body_parts),
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
                body=payload if response_allows_body(status) and not self.head_only else b"",
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
        if self._body_channel in {"file", "pathsend"}:
            raise ASGIProtocolError("http.response.body cannot follow streamed file response")
        self._body_channel = "body"

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
            await self._start_body_response(body, more_body, body_allowed, status_allows_body)
            return

        if self.finished:
            raise ASGIProtocolError("response body sent after response completion")
        if body and body_allowed:
            self.writer.write(serialize_http11_response_chunk(body) if self.chunked else body)
        if not more_body:
            if self.chunked:
                self.writer.write(finalize_chunked_body())
            self.finished = True
        await self.writer.drain()

    async def _start_body_response(
        self,
        body: bytes,
        more_body: bool,
        body_allowed: bool,
        status_allows_body: bool,
    ) -> None:
        assert self.status is not None
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
            self.writer.write(serialize_http11_response_chunk(body) if self.chunked else body)
        if not more_body:
            if self.chunked:
                self.writer.write(finalize_chunked_body())
            self.finished = True
        await self.writer.drain()

    async def _handle_response_file(self, message: dict, *, from_pathsend: bool = False) -> None:
        if self.status is None:
            raise ASGIProtocolError("tigrcorn.http.response.file sent before final http.response.start")
        if self._body_channel == "body":
            raise ASGIProtocolError("tigrcorn.http.response.file cannot follow buffered body events")
        if self._body_channel == "pathsend" and not from_pathsend:
            raise ASGIProtocolError("tigrcorn.http.response.file cannot follow http.response.pathsend")
        if from_pathsend:
            if self._body_channel is not None:
                raise ASGIProtocolError("http.response.pathsend cannot be mixed with buffered or streamed body events")
            self._body_channel = "pathsend"
        elif self._body_channel is None:
            self._body_channel = "file"
        if self.finished:
            raise ASGIProtocolError("response body sent after response completion")
        segments = normalize_response_file_segments(message.get("segments"))
        more_body = bool(message.get("more_body", False))
        if from_pathsend and more_body:
            raise ASGIProtocolError("http.response.pathsend does not support more_body")
        has_len = get_header(self.headers, b"content-length") is not None
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
                self.writer.write(serialize_http11_response_chunk(chunk) if self.chunked else chunk)
                await self.writer.drain()
        if not more_body:
            if self.chunked:
                self.writer.write(finalize_chunked_body())
                await self.writer.drain()
            self.finished = True

    async def _handle_response_pathsend(self, message: dict) -> None:
        segment = normalize_response_pathsend_segment(message.get("path"))
        await self._handle_response_file(
            {
                "type": "tigrcorn.http.response.file",
                "segments": [segment],
                "more_body": False,
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
