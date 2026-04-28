from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class BufferLimits:
    read_limit: int = 64 * 1024
    write_limit: int = 64 * 1024


@dataclass(slots=True)
class ByteBuffer:
    limit: int = 64 * 1024
    data: bytearray = field(default_factory=bytearray)

    def append(self, payload: bytes) -> None:
        if len(self.data) + len(payload) > self.limit:
            raise BufferError('buffer limit exceeded')
        self.data.extend(payload)

    def take(self, n: int = -1) -> bytes:
        if n < 0 or n >= len(self.data):
            payload = bytes(self.data)
            self.data.clear()
            return payload
        payload = bytes(self.data[:n])
        del self.data[:n]
        return payload
