from __future__ import annotations

from tigrcorn_core.errors import ProtocolError


_TCHAR = frozenset(b"!#$%&'*+-.^_`|~0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz")


def _is_token(value: bytes) -> bool:
    return bool(value) and all(byte in _TCHAR for byte in value)


def _validate_header_name(name: bytes) -> None:
    if not _is_token(name):
        raise ProtocolError('invalid header field name')


def _validate_header_value(value: bytes) -> None:
    for byte in value:
        if byte in {0x00, 0x0A, 0x0D} or (byte < 0x20 and byte != 0x09):
            raise ProtocolError('invalid header field value')
