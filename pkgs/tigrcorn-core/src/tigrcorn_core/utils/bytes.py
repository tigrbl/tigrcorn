from __future__ import annotations

from collections.abc import Iterable, Iterator


def clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


def split_chunks(data: bytes, size: int) -> Iterator[bytes]:
    if size <= 0:
        raise ValueError("size must be positive")
    for offset in range(0, len(data), size):
        yield data[offset : offset + size]


def encode_u24(value: int) -> bytes:
    if not 0 <= value <= 0xFFFFFF:
        raise ValueError("u24 out of range")
    return value.to_bytes(3, "big")


def decode_u24(data: bytes) -> int:
    if len(data) != 3:
        raise ValueError("u24 requires exactly 3 bytes")
    return int.from_bytes(data, "big")


def xor_bytes(left: bytes, right: bytes) -> bytes:
    if len(left) != len(right):
        raise ValueError("buffers must have equal length")
    return bytes(a ^ b for a, b in zip(left, right))


def encode_quic_varint(value: int) -> bytes:
    if value < 0:
        raise ValueError("varint must be non-negative")
    if value < 2**6:
        return bytes([value])
    if value < 2**14:
        raw = value | 0x4000
        return raw.to_bytes(2, "big")
    if value < 2**30:
        raw = value | 0x80000000
        return raw.to_bytes(4, "big")
    if value < 2**62:
        raw = value | 0xC000000000000000
        return raw.to_bytes(8, "big")
    raise ValueError("varint too large")


def decode_quic_varint(data: bytes, offset: int = 0) -> tuple[int, int]:
    if offset >= len(data):
        raise ValueError("buffer underflow")
    first = data[offset]
    prefix = first >> 6
    length = 1 << prefix
    end = offset + length
    if end > len(data):
        raise ValueError("buffer underflow")
    value = int.from_bytes(data[offset:end], "big")
    mask = (1 << (length * 8 - 2)) - 1
    return value & mask, end


def pack_varbytes(payload: bytes) -> bytes:
    return encode_quic_varint(len(payload)) + payload


def unpack_varbytes(data: bytes, offset: int = 0) -> tuple[bytes, int]:
    length, offset = decode_quic_varint(data, offset)
    end = offset + length
    if end > len(data):
        raise ValueError("buffer underflow")
    return data[offset:end], end


def join_bytes(parts: Iterable[bytes]) -> bytes:
    return b"".join(parts)
