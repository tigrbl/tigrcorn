from __future__ import annotations

from .imports import *
from .vectors import *

def encode_server_name(server_name: str) -> bytes:
    encoded = server_name.encode('utf-8')
    entry = b'\x00' + _u16_vector(encoded)
    return _u16_vector(entry)



def decode_server_name(data: bytes) -> str:
    names_raw, offset = _read_u16_vector(data, 0)
    if offset != len(data):
        raise ProtocolError('invalid server_name extension')
    inner = 0
    while inner < len(names_raw):
        name_type, inner = _read_u8(names_raw, inner)
        name, inner = _read_u16_vector(names_raw, inner)
        if name_type == 0:
            return name.decode('utf-8')
    raise ProtocolError('server_name extension does not contain a host_name entry')



def encode_supported_versions_client(versions: Sequence[int]) -> bytes:
    payload = b''.join(version.to_bytes(2, 'big') for version in versions)
    return _u8_vector(payload)



def decode_supported_versions_client(data: bytes) -> tuple[int, ...]:
    payload, offset = _read_u8_vector(data, 0)
    if offset != len(data) or len(payload) % 2:
        raise ProtocolError('invalid supported_versions extension')
    return tuple(int.from_bytes(payload[index:index + 2], 'big') for index in range(0, len(payload), 2))



def encode_supported_versions_server(version: int) -> bytes:
    return version.to_bytes(2, 'big')



def decode_supported_versions_server(data: bytes) -> int:
    if len(data) != 2:
        raise ProtocolError('invalid selected supported_versions extension')
    return int.from_bytes(data, 'big')



def encode_supported_groups(groups: Sequence[int]) -> bytes:
    payload = b''.join(group.to_bytes(2, 'big') for group in groups)
    return _u16_vector(payload)



def decode_supported_groups(data: bytes) -> tuple[int, ...]:
    payload, offset = _read_u16_vector(data, 0)
    if offset != len(data) or len(payload) % 2:
        raise ProtocolError('invalid supported_groups extension')
    return tuple(int.from_bytes(payload[index:index + 2], 'big') for index in range(0, len(payload), 2))



def encode_signature_algorithms(schemes: Sequence[int]) -> bytes:
    payload = b''.join(scheme.to_bytes(2, 'big') for scheme in schemes)
    return _u16_vector(payload)



def decode_signature_algorithms(data: bytes) -> tuple[int, ...]:
    payload, offset = _read_u16_vector(data, 0)
    if offset != len(data) or len(payload) % 2:
        raise ProtocolError('invalid signature_algorithms extension')
    return tuple(int.from_bytes(payload[index:index + 2], 'big') for index in range(0, len(payload), 2))



def encode_alpn(protocols: Sequence[str]) -> bytes:
    payload = bytearray()
    for protocol in protocols:
        raw = protocol.encode('ascii')
        payload.extend(_u8_vector(raw))
    return _u16_vector(bytes(payload))



def decode_alpn(data: bytes) -> tuple[str, ...]:
    payload, offset = _read_u16_vector(data, 0)
    if offset != len(data):
        raise ProtocolError('invalid ALPN extension')
    inner = 0
    protocols: list[str] = []
    while inner < len(payload):
        raw, inner = _read_u8_vector(payload, inner)
        protocols.append(raw.decode('ascii'))
    if not protocols:
        raise ProtocolError('ALPN extension is empty')
    return tuple(protocols)



def encode_psk_key_exchange_modes(modes: Sequence[int]) -> bytes:
    return _u8_vector(bytes(modes))



def decode_psk_key_exchange_modes(data: bytes) -> tuple[int, ...]:
    payload, offset = _read_u8_vector(data, 0)
    if offset != len(data):
        raise ProtocolError('invalid psk_key_exchange_modes extension')
    return tuple(payload)

__all__ = [name for name in globals() if not name.startswith('__')]
