from __future__ import annotations

from collections.abc import Iterable


def normalize_headers(headers: Iterable[tuple[bytes, bytes]]) -> list[tuple[bytes, bytes]]:
    return [(bytes(k).lower(), bytes(v)) for k, v in headers]


def get_header(headers: Iterable[tuple[bytes, bytes]], name: bytes) -> bytes | None:
    wanted = name.lower()
    for key, value in headers:
        if key.lower() == wanted:
            return value
    return None


def get_headers(headers: Iterable[tuple[bytes, bytes]], name: bytes) -> list[bytes]:
    wanted = name.lower()
    return [value for key, value in headers if key.lower() == wanted]


def header_contains_token(headers: Iterable[tuple[bytes, bytes]], name: bytes, token: bytes) -> bool:
    wanted_name = name.lower()
    wanted_token = token.lower()
    for key, value in headers:
        if key.lower() != wanted_name:
            continue
        values = [part.strip().lower() for part in value.split(b",")]
        if wanted_token in values:
            return True
    return False


def append_if_missing(headers: list[tuple[bytes, bytes]], name: bytes, value: bytes) -> None:
    if get_header(headers, name) is None:
        headers.append((name.lower(), value))


def strip_connection_specific_headers(headers: Iterable[tuple[bytes, bytes]]) -> list[tuple[bytes, bytes]]:
    banned = {
        b"connection",
        b"keep-alive",
        b"proxy-connection",
        b"transfer-encoding",
        b"upgrade",
    }
    return [(k, v) for k, v in headers if k.lower() not in banned]
