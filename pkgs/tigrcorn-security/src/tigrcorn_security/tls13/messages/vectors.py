from __future__ import annotations

from .imports import *
from .types import *

def _u8_vector(payload: bytes) -> bytes:
    if len(payload) > 255:
        raise ValueError('u8 vector too large')
    return bytes([len(payload)]) + payload



def _u16_vector(payload: bytes) -> bytes:
    if len(payload) > 0xFFFF:
        raise ValueError('u16 vector too large')
    return len(payload).to_bytes(2, 'big') + payload



def _u24_vector(payload: bytes) -> bytes:
    if len(payload) > 0xFFFFFF:
        raise ValueError('u24 vector too large')
    return len(payload).to_bytes(3, 'big') + payload



def _read_exact(data: bytes, offset: int, length: int) -> tuple[bytes, int]:
    end = offset + length
    if end > len(data):
        raise NeedMoreData('incomplete TLS handshake payload')
    return data[offset:end], end



def _read_u8(data: bytes, offset: int) -> tuple[int, int]:
    raw, offset = _read_exact(data, offset, 1)
    return raw[0], offset



def _read_u16(data: bytes, offset: int) -> tuple[int, int]:
    raw, offset = _read_exact(data, offset, 2)
    return int.from_bytes(raw, 'big'), offset



def _read_u24(data: bytes, offset: int) -> tuple[int, int]:
    raw, offset = _read_exact(data, offset, 3)
    return int.from_bytes(raw, 'big'), offset



def _read_u32(data: bytes, offset: int) -> tuple[int, int]:
    raw, offset = _read_exact(data, offset, 4)
    return int.from_bytes(raw, 'big'), offset



def _read_u8_vector(data: bytes, offset: int) -> tuple[bytes, int]:
    length, offset = _read_u8(data, offset)
    return _read_exact(data, offset, length)



def _read_u16_vector(data: bytes, offset: int) -> tuple[bytes, int]:
    length, offset = _read_u16(data, offset)
    return _read_exact(data, offset, length)



def _read_u24_vector(data: bytes, offset: int) -> tuple[bytes, int]:
    length, offset = _read_u24(data, offset)
    return _read_exact(data, offset, length)

__all__ = [name for name in globals() if not name.startswith('__')]
