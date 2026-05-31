from __future__ import annotations

from collections.abc import Iterable, Mapping
from email.utils import formatdate
from typing import Any


HeaderPair = tuple[bytes, bytes]

_EARLY_HINT_SAFE_HEADERS = {b"link"}


def _to_bytes(value: bytes | bytearray | memoryview | str) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return value.encode('latin1')
    return bytes(value)


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


def replace_header(headers: list[HeaderPair], name: bytes, value: bytes | None) -> list[HeaderPair]:
    wanted = name.lower()
    filtered = [(key, item_value) for key, item_value in headers if key.lower() != wanted]
    if value is not None:
        filtered.append((wanted, value))
    return filtered


def strip_connection_specific_headers(headers: Iterable[tuple[bytes, bytes]]) -> list[tuple[bytes, bytes]]:
    banned = {
        b"connection",
        b"keep-alive",
        b"proxy-connection",
        b"transfer-encoding",
        b"upgrade",
    }
    return [(k, v) for k, v in headers if k.lower() not in banned]


def http_date_now() -> bytes:
    return formatdate(usegmt=True).encode('ascii')


def parse_header_entry(value: Any) -> HeaderPair:
    if isinstance(value, Mapping):
        name = value.get('name')
        header_value = value.get('value')
        if name is None or header_value is None:
            raise ValueError('header mappings require name and value keys')
        return _to_bytes(name).lower(), _to_bytes(header_value)
    if isinstance(value, (tuple, list)) and len(value) == 2:
        name, header_value = value
        return _to_bytes(name).lower(), _to_bytes(header_value)
    if isinstance(value, str):
        if ':' not in value:
            raise ValueError('header entries must use name:value syntax')
        name, header_value = value.split(':', 1)
        name_b = name.strip().encode('latin1').lower()
        value_b = header_value.strip().encode('latin1')
        if not name_b:
            raise ValueError('header name cannot be empty')
        return name_b, value_b
    raise ValueError(f'unsupported header entry: {value!r}')


def normalize_header_entries(values: Iterable[Any] | Any | None) -> list[HeaderPair]:
    if values is None:
        return []
    if isinstance(values, (str, bytes, bytearray, memoryview, Mapping)):
        values = [values]
    normalized: list[HeaderPair] = []
    for item in values:
        normalized.append(parse_header_entry(item))
    return normalized


def normalize_alt_svc_entries(values: Iterable[Any] | Any | None) -> list[bytes]:
    if values is None:
        return []
    if isinstance(values, (str, bytes, bytearray, memoryview)):
        values = [values]
    normalized: list[bytes] = []
    for item in values:
        value = _to_bytes(item).strip()
        if value:
            normalized.append(value)
    return normalized


def sanitize_early_hints_headers(headers: Iterable[tuple[bytes, bytes]]) -> list[HeaderPair]:
    normalized = strip_connection_specific_headers(headers)
    return [
        (bytes(name).lower(), bytes(value))
        for name, value in normalized
        if bytes(name).lower() in _EARLY_HINT_SAFE_HEADERS
    ]


def apply_response_header_policy(
    headers: Iterable[tuple[bytes, bytes]],
    *,
    server_header: bytes | None = None,
    include_date_header: bool = True,
    default_headers: Iterable[Any] = (),
    alt_svc_values: Iterable[Any] = (),
) -> list[HeaderPair]:
    normalized = [(bytes(k).lower(), bytes(v)) for k, v in headers]
    for name, value in normalize_header_entries(default_headers):
        append_if_missing(normalized, name, value)
    if include_date_header:
        append_if_missing(normalized, b'date', http_date_now())
    if server_header:
        append_if_missing(normalized, b'server', server_header)
    if get_header(normalized, b'alt-svc') is None:
        for value in normalize_alt_svc_entries(alt_svc_values):
            normalized.append((b'alt-svc', value))
    return normalized
