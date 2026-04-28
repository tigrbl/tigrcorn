from __future__ import annotations

import struct
from dataclasses import dataclass


@dataclass(slots=True)
class RawFrame:
    payload: bytes

    @property
    def length(self) -> int:
        return len(self.payload)


def encode_frame(payload: bytes) -> bytes:
    return struct.pack("!I", len(payload)) + payload


def try_decode_frame(buffer: bytearray) -> RawFrame | None:
    if len(buffer) < 4:
        return None
    size = struct.unpack("!I", buffer[:4])[0]
    if len(buffer) < 4 + size:
        return None
    payload = bytes(buffer[4 : 4 + size])
    del buffer[: 4 + size]
    return RawFrame(payload)
