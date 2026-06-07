from __future__ import annotations

from .imports import *
from .vectors import *

def encode_keyshare_client(shares: Sequence[tuple[int, bytes]]) -> bytes:
    payload = bytearray()
    for group, key_exchange in shares:
        payload.extend(group.to_bytes(2, 'big'))
        payload.extend(_u16_vector(key_exchange))
    return _u16_vector(bytes(payload))



def decode_keyshare_client(data: bytes) -> dict[int, bytes]:
    payload, offset = _read_u16_vector(data, 0)
    if offset != len(data):
        raise ProtocolError('invalid key_share extension')
    inner = 0
    shares: dict[int, bytes] = {}
    while inner < len(payload):
        group, inner = _read_u16(payload, inner)
        key_exchange, inner = _read_u16_vector(payload, inner)
        shares[group] = key_exchange
    return shares



def encode_keyshare_server(group: int, key_exchange: bytes) -> bytes:
    return group.to_bytes(2, 'big') + _u16_vector(key_exchange)



def decode_keyshare_server(data: bytes) -> tuple[int, bytes]:
    group, offset = _read_u16(data, 0)
    key_exchange, offset = _read_u16_vector(data, offset)
    if offset != len(data):
        raise ProtocolError('invalid server key_share extension')
    return group, key_exchange



def encode_keyshare_hrr(selected_group: int) -> bytes:
    return selected_group.to_bytes(2, 'big')



def decode_keyshare_hrr(data: bytes) -> int:
    if len(data) != 2:
        raise ProtocolError('invalid HelloRetryRequest key_share extension')
    return int.from_bytes(data, 'big')



def encode_cookie(cookie: bytes) -> bytes:
    return _u16_vector(cookie)



def decode_cookie(data: bytes) -> bytes:
    cookie, offset = _read_u16_vector(data, 0)
    if offset != len(data):
        raise ProtocolError('invalid cookie extension')
    return cookie

__all__ = [name for name in globals() if not name.startswith('__')]
