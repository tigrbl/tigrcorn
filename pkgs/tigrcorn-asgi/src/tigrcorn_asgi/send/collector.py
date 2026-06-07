from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import dataclass, field

from tigrcorn_asgi.errors import ASGIProtocolError

from .helpers import format_strong_etag
from .materialize import materialize_response_body_segments
from .segments import BodySegment, FileBodySegment
from .validation import normalize_response_file_segments, normalize_response_pathsend_segment


def _default_spool_threshold() -> int:
    from tigrcorn_asgi import send

    return int(send.DEFAULT_RESPONSE_BODY_SPOOL_THRESHOLD)


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
    spool_threshold: int = field(default_factory=_default_spool_threshold)
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
        return format_strong_etag(self._body_digest.hexdigest().encode("ascii"))

    def _ensure_spool_file(self) -> None:
        if self._spool_handle is not None and self._spool_path is not None:
            return
        handle = tempfile.NamedTemporaryFile(prefix="tigrcorn-response-", suffix=".bin", delete=False)
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
            return b"".join(self.body_parts)
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
            self._handle_response_start(message)
            return
        if message_type == "http.response.body":
            self._handle_response_body(message)
            return
        if message_type == "tigrcorn.http.response.file":
            self._handle_response_file(message)
            return
        if message_type == "http.response.pathsend":
            self._handle_response_pathsend(message)
            return
        if message_type == "http.response.trailers":
            self._handle_response_trailers(message)
            return
        raise ASGIProtocolError(f"unexpected HTTP send event: {message_type!r}")

    def _handle_response_start(self, message: dict) -> None:
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

    def _handle_response_body(self, message: dict) -> None:
        if self.status is None:
            raise ASGIProtocolError("http.response.body sent before final http.response.start")
        if self._body_channel in {"file", "pathsend"}:
            raise ASGIProtocolError("http.response.body cannot follow streamed file response")
        self._body_channel = "body"
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

    def _handle_response_file(self, message: dict) -> None:
        if self.status is None:
            raise ASGIProtocolError("tigrcorn.http.response.file sent before final http.response.start")
        if self.body_parts or self.has_spooled_body() or self._body_channel == "body":
            raise ASGIProtocolError("tigrcorn.http.response.file cannot follow buffered body events")
        if self._body_channel == "pathsend":
            raise ASGIProtocolError("tigrcorn.http.response.file cannot follow http.response.pathsend")
        self._body_channel = "file"
        self.uses_streamed_body = True
        self.body_segments.extend(normalize_response_file_segments(message.get("segments")))
        self.complete = not bool(message.get("more_body", False))

    def _handle_response_pathsend(self, message: dict) -> None:
        if self.status is None:
            raise ASGIProtocolError("http.response.pathsend sent before final http.response.start")
        if self.body_parts or self.has_spooled_body() or self._body_channel is not None:
            raise ASGIProtocolError("http.response.pathsend cannot be mixed with buffered or streamed body events")
        if bool(message.get("more_body", False)):
            raise ASGIProtocolError("http.response.pathsend does not support more_body")
        self._body_channel = "pathsend"
        self.uses_streamed_body = True
        self.body_segments.append(normalize_response_pathsend_segment(message.get("path")))
        self.complete = True

    def _handle_response_trailers(self, message: dict) -> None:
        if self.status is None:
            raise ASGIProtocolError("http.response.trailers sent before final http.response.start")
        self.trailers.extend(list(message.get("trailers", [])))
        self.complete = not bool(message.get("more_trailers", False))

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
            body = b"".join(self.body_parts)
        else:
            with open(self._spool_path, "rb") as handle:
                body = handle.read()
        return self.status, self.headers, body, list(self.trailers)
