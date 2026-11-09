from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tigrcorn_asgi.send import FileBodySegment, MemoryBodySegment


HeaderList = list[tuple[bytes, bytes]]
PRECOMPRESSED_SIDECAR_SUFFIXES: dict[str, str] = {"br": ".br", "gzip": ".gz"}
BUFFERED_DYNAMIC_CODING_MAX_BYTES = 256 * 1024
MAX_ETAG_CACHE_ENTRIES = 1024


@dataclass(slots=True)
class StaticFileResponse:
    status: int
    headers: HeaderList
    body: bytes = b""
    segments: tuple[MemoryBodySegment | FileBodySegment, ...] = ()
    preprocessed: bool = False


@dataclass(frozen=True, slots=True)
class StaticPathDecision:
    accepted: bool
    normalized_path: str | None
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "normalized_path": self.normalized_path,
            "reason": self.reason,
        }


@dataclass(slots=True)
class SelectedRepresentation:
    path: Path
    content_encoding: str | None
    mtime: float
    size: int
    mtime_ns: int
