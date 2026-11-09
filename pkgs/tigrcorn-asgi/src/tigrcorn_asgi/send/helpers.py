from __future__ import annotations

from pathlib import Path

from .segments import BodySegment, MemoryBodySegment


def format_strong_etag(value: bytes | str) -> bytes:
    if isinstance(value, bytes):
        text = value.decode("latin1")
    else:
        text = value
    opaque = text.replace("\\", "\\\\").replace('"', '\\"').encode("latin1")
    return b'"' + opaque + b'"'


def segment_length(segment: BodySegment) -> int:
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
    return any(segment_length(segment) > 0 for segment in segments)
