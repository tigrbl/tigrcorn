from __future__ import annotations

from dataclasses import dataclass

from .base import BaseSession


@dataclass(slots=True)
class QuicSession(BaseSession):
    protocol: str = 'quic'
    stream_count: int = 0

    def opened_stream(self) -> None:
        self.stream_count += 1
