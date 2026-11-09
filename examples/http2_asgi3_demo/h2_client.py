from __future__ import annotations

import socket
import threading
import time
from dataclasses import dataclass

from tigrcorn.constants import H2_PREFACE
from tigrcorn.protocols.http2.codec import (
    FLAG_END_STREAM,
    FRAME_DATA,
    FRAME_HEADERS,
    FRAME_SETTINGS,
    FRAME_WINDOW_UPDATE,
    FrameBuffer,
    FrameWriter,
    decode_settings,
    serialize_frame,
    serialize_settings,
)
from tigrcorn.protocols.http2.hpack import HPACKDecoder, encode_header_block


@dataclass
class H2Response:
    stream_id: int
    status: int | None
    headers: list[tuple[str, str]]
    body: bytes
    elapsed_ms: float


def _header_text(headers: list[tuple[bytes, bytes]]) -> list[tuple[str, str]]:
    return [(name.decode("latin-1"), value.decode("latin-1")) for name, value in headers]


class H2PriorKnowledgeClient:
    def __init__(self, host: str, port: int, *, authority: str = "tigrcorn-h2-app") -> None:
        self.host = host
        self.port = port
        self.authority = authority
        self._writer = FrameWriter()
        self._next_stream_id = 1
        self._lock = threading.Lock()

    def request(self, method: str, path: str, body: bytes = b"", headers: list[tuple[bytes, bytes]] | None = None) -> H2Response:
        with socket.create_connection((self.host, self.port), timeout=8) as sock:
            sock.settimeout(8)
            stream_id = self._next_id()
            started = time.perf_counter()
            sock.sendall(H2_PREFACE)
            sock.sendall(serialize_settings({}))

            request_headers = [
                (b":method", method.upper().encode("ascii")),
                (b":scheme", b"http"),
                (b":path", path.encode("ascii")),
                (b":authority", self.authority.encode("ascii")),
            ]
            if body:
                request_headers.append((b"content-length", str(len(body)).encode("ascii")))
            request_headers.extend(headers or [])
            block = encode_header_block(request_headers)
            sock.sendall(self._writer.headers(stream_id, block, end_stream=not body))
            if body:
                sock.sendall(self._writer.data(stream_id, body, end_stream=True))
            return self._read_response(sock, stream_id, started)

    def multiplex_get(self, paths: list[str]) -> list[H2Response]:
        with socket.create_connection((self.host, self.port), timeout=8) as sock:
            sock.settimeout(8)
            sock.sendall(H2_PREFACE)
            sock.sendall(serialize_settings({}))
            started_by_stream: dict[int, float] = {}
            for path in paths:
                stream_id = self._next_id()
                started_by_stream[stream_id] = time.perf_counter()
                block = encode_header_block(
                    [
                        (b":method", b"GET"),
                        (b":scheme", b"http"),
                        (b":path", path.encode("ascii")),
                        (b":authority", self.authority.encode("ascii")),
                    ]
                )
                sock.sendall(self._writer.headers(stream_id, block, end_stream=True))
            return self._read_responses(sock, started_by_stream)

    def _next_id(self) -> int:
        with self._lock:
            stream_id = self._next_stream_id
            self._next_stream_id += 2
            return stream_id

    def _read_response(self, sock: socket.socket, stream_id: int, started: float) -> H2Response:
        buf = FrameBuffer()
        decoder = HPACKDecoder()
        header_pairs: list[tuple[bytes, bytes]] = []
        body = bytearray()
        status: int | None = None
        ended = False
        while not ended:
            data = sock.recv(65535)
            if not data:
                break
            buf.feed(data)
            for frame in buf.pop_all():
                if frame.frame_type == FRAME_SETTINGS and frame.payload:
                    decode_settings(frame.payload)
                elif frame.frame_type == FRAME_HEADERS and frame.stream_id == stream_id:
                    decoded = decoder.decode_header_block(frame.payload)
                    header_pairs.extend(decoded)
                    for name, value in decoded:
                        if name == b":status":
                            status = int(value)
                    if frame.flags & FLAG_END_STREAM:
                        ended = True
                elif frame.frame_type == FRAME_DATA and frame.stream_id == stream_id:
                    body.extend(frame.payload)
                    increment = len(frame.payload).to_bytes(4, "big")
                    sock.sendall(serialize_frame(FRAME_WINDOW_UPDATE, 0, 0, increment))
                    sock.sendall(serialize_frame(FRAME_WINDOW_UPDATE, 0, stream_id, increment))
                    if frame.flags & FLAG_END_STREAM:
                        ended = True
        elapsed_ms = (time.perf_counter() - started) * 1000
        return H2Response(stream_id, status, _header_text(header_pairs), bytes(body), elapsed_ms)

    def _read_responses(self, sock: socket.socket, started_by_stream: dict[int, float]) -> list[H2Response]:
        buf = FrameBuffer()
        decoder = HPACKDecoder()
        headers_by_stream: dict[int, list[tuple[bytes, bytes]]] = {stream_id: [] for stream_id in started_by_stream}
        bodies_by_stream: dict[int, bytearray] = {stream_id: bytearray() for stream_id in started_by_stream}
        statuses: dict[int, int | None] = {stream_id: None for stream_id in started_by_stream}
        completed: set[int] = set()
        while len(completed) < len(started_by_stream):
            data = sock.recv(65535)
            if not data:
                break
            buf.feed(data)
            for frame in buf.pop_all():
                stream_id = frame.stream_id
                if frame.frame_type == FRAME_SETTINGS and frame.payload:
                    decode_settings(frame.payload)
                elif frame.frame_type == FRAME_HEADERS and stream_id in started_by_stream:
                    decoded = decoder.decode_header_block(frame.payload)
                    headers_by_stream[stream_id].extend(decoded)
                    for name, value in decoded:
                        if name == b":status":
                            statuses[stream_id] = int(value)
                    if frame.flags & FLAG_END_STREAM:
                        completed.add(stream_id)
                elif frame.frame_type == FRAME_DATA and stream_id in started_by_stream:
                    bodies_by_stream[stream_id].extend(frame.payload)
                    increment = len(frame.payload).to_bytes(4, "big")
                    sock.sendall(serialize_frame(FRAME_WINDOW_UPDATE, 0, 0, increment))
                    sock.sendall(serialize_frame(FRAME_WINDOW_UPDATE, 0, stream_id, increment))
                    if frame.flags & FLAG_END_STREAM:
                        completed.add(stream_id)
        now = time.perf_counter()
        return [
            H2Response(
                stream_id,
                statuses[stream_id],
                _header_text(headers_by_stream[stream_id]),
                bytes(bodies_by_stream[stream_id]),
                (now - started_by_stream[stream_id]) * 1000,
            )
            for stream_id in sorted(started_by_stream)
        ]
