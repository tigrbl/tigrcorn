from __future__ import annotations

import os
from pathlib import Path

from tigrcorn_asgi.errors import ASGIProtocolError

from .segments import BodySegment, FileBodySegment, MemoryBodySegment


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
            raise ASGIProtocolError(f"invalid tigrcorn.http.response.file segment: {raw!r}")
        segment_type = str(raw.get("type", "file")).lower()
        if segment_type == "memory":
            segments.append(MemoryBodySegment(bytes(raw.get("body", b""))))
            continue
        if segment_type != "file":
            raise ASGIProtocolError(f"unsupported tigrcorn.http.response.file segment type: {segment_type!r}")
        count_raw = raw.get("count")
        segments.append(
            FileBodySegment(
                path=os.fspath(raw["path"]),
                offset=int(raw.get("offset", 0)),
                count=None if count_raw is None else int(count_raw),
            )
        )
    return segments


def normalize_response_pathsend_segment(raw_path: object) -> FileBodySegment:
    path = os.fspath(raw_path)
    if not os.path.isabs(path):
        raise ASGIProtocolError("http.response.pathsend requires an absolute file path")
    candidate = Path(path)
    try:
        size = candidate.stat().st_size
    except FileNotFoundError as exc:
        raise ASGIProtocolError("http.response.pathsend requires an existing file path") from exc
    if not candidate.is_file():
        raise ASGIProtocolError("http.response.pathsend requires a regular file path")
    return FileBodySegment(path, 0, size)
