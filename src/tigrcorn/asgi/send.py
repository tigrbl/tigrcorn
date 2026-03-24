from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from tigrcorn.asgi.errors import ASGIProtocolError
from tigrcorn.protocols.content_coding import apply_http_content_coding
from tigrcorn.protocols.http1.serializer import (
    finalize_chunked_body,
    response_allows_body,
    serialize_http11_response_head,
    serialize_http11_response_whole,
    serialize_http11_response_chunk,
)
from tigrcorn.utils.headers import get_header


@dataclass(slots=True)
class HTTPResponseCollector:
    status: int | None = None
    headers: list[tuple[bytes, bytes]] = field(default_factory=list)
    body_parts: list[bytes] = field(default_factory=list)
    trailers: list[tuple[bytes, bytes]] = field(default_factory=list)
    complete: bool = False
    informational_responses: list[tuple[int, list[tuple[bytes, bytes]]]] = field(default_factory=list)

    async def __call__(self, message: dict) -> None:
        message_type = message["type"]
        if message_type == "http.response.start":
            status = int(message["status"])
            headers = list(message.get("headers", []))
            if status < 200:
                if self.status is not None or self.body_parts or self.complete:
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
            self.body_parts.append(message.get("body", b""))
            self.complete = not bool(message.get("more_body", False))
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

    def response_tuple(self) -> tuple[int, list[tuple[bytes, bytes]], bytes, list[tuple[bytes, bytes]]]:
        self.finalize()
        assert self.status is not None
        return self.status, self.headers, b"".join(self.body_parts), list(self.trailers)


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
    ) -> None:
        self.writer = writer
        self.keep_alive = keep_alive
        self.server_header = server_header
        self.method = method.upper()
        self.request_headers = list(request_headers)
        self.content_coding_policy = content_coding_policy
        self.content_codings = tuple(content_codings)
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

    async def __call__(self, message: dict) -> None:
        typ = message["type"]
        if typ == "http.response.start":
            await self._handle_response_start(message)
            return
        if typ == "http.response.trailers":
            await self._handle_response_trailers(message)
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
            )
        else:
            raw = serialize_http11_response_whole(
                status=status,
                headers=headers,
                body=payload if response_allows_body(status) and not self.head_only else b'',
                keep_alive=self.keep_alive,
                server_header=self.server_header,
            )
        self.writer.write(raw)
        await self.writer.drain()
        self.started = True
        self.finished = True

    async def _handle_response_body(self, message: dict) -> None:
        if self.status is None:
            raise ASGIProtocolError("http.response.body sent before final http.response.start")

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
                    )
                else:
                    payload = body if body_allowed else b""
                    raw = serialize_http11_response_whole(
                        status=self.status,
                        headers=self.headers,
                        body=payload,
                        keep_alive=self.keep_alive,
                        server_header=self.server_header,
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
