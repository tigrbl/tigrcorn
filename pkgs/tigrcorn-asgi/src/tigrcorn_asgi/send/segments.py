from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MemoryBodySegment:
    data: bytes


@dataclass(frozen=True, slots=True)
class FileBodySegment:
    path: str
    offset: int = 0
    count: int | None = None


BodySegment = MemoryBodySegment | FileBodySegment
