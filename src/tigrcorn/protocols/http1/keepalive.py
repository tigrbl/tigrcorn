from __future__ import annotations

from tigrcorn.utils.headers import get_header, header_contains_token


def keep_alive_for_request(http_version: str, headers: list[tuple[bytes, bytes]]) -> bool:
    if http_version == "1.0":
        return header_contains_token(headers, b"connection", b"keep-alive")
    if header_contains_token(headers, b"connection", b"close"):
        return False
    return True


def expect_continue(headers: list[tuple[bytes, bytes]]) -> bool:
    value = get_header(headers, b"expect")
    return bool(value and value.lower() == b"100-continue")
