from __future__ import annotations

from .collector import HTTPResponseCollector
from .helpers import response_body_segments_have_bytes
from .lifespan import LifespanSend
from .materialize import iter_response_body_segments, materialize_response_body_segments
from .segments import BodySegment, FileBodySegment, MemoryBodySegment
from .validation import normalize_response_file_segments, normalize_response_pathsend_segment
from .writer import HTTPResponseWriter

__all__ = [
    "BodySegment",
    "DEFAULT_RESPONSE_BODY_SPOOL_THRESHOLD",
    "FileBodySegment",
    "HTTPResponseCollector",
    "HTTPResponseWriter",
    "LifespanSend",
    "MemoryBodySegment",
    "iter_response_body_segments",
    "materialize_response_body_segments",
    "normalize_response_file_segments",
    "normalize_response_pathsend_segment",
    "response_body_segments_have_bytes",
]


DEFAULT_RESPONSE_BODY_SPOOL_THRESHOLD = 256 * 1024
