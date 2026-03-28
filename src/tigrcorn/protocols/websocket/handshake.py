from __future__ import annotations

import base64
import hashlib

from tigrcorn.errors import ProtocolError
from tigrcorn.utils.headers import apply_response_header_policy, get_header, header_contains_token

_MAGIC = b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def is_websocket_upgrade(method: str, headers: list[tuple[bytes, bytes]]) -> bool:
    return (
        method.upper() == "GET"
        and header_contains_token(headers, b"connection", b"upgrade")
        and header_contains_token(headers, b"upgrade", b"websocket")
    )


def websocket_accept_value(sec_websocket_key: bytes) -> bytes:
    sha = hashlib.sha1(sec_websocket_key + _MAGIC).digest()
    return base64.b64encode(sha)


def validate_client_handshake(headers: list[tuple[bytes, bytes]]) -> bytes:
    version = get_header(headers, b"sec-websocket-version")
    if version != b"13":
        raise ProtocolError("unsupported websocket version")
    key = get_header(headers, b"sec-websocket-key")
    if not key:
        raise ProtocolError("missing Sec-WebSocket-Key")
    try:
        decoded = base64.b64decode(key, validate=True)
    except Exception as exc:
        raise ProtocolError("invalid Sec-WebSocket-Key") from exc
    if len(decoded) != 16:
        raise ProtocolError("invalid Sec-WebSocket-Key length")
    return key


def build_handshake_response(
    sec_websocket_key: bytes,
    *,
    subprotocol: str | None = None,
    headers: list[tuple[bytes, bytes]] | None = None,
    server_header: bytes | None = None,
    include_date_header: bool = True,
    default_headers: list[tuple[bytes, bytes]] | tuple[tuple[bytes, bytes], ...] = (),
) -> bytes:
    response_headers = [
        (b"upgrade", b"websocket"),
        (b"connection", b"Upgrade"),
        (b"sec-websocket-accept", websocket_accept_value(sec_websocket_key)),
    ]
    if subprotocol:
        response_headers.append((b"sec-websocket-protocol", subprotocol.encode("ascii")))
    if headers:
        response_headers.extend([(k.lower(), v) for k, v in headers])
    response_headers = apply_response_header_policy(
        response_headers,
        server_header=server_header,
        include_date_header=include_date_header,
        default_headers=default_headers,
    )
    lines = [b"HTTP/1.1 101 Switching Protocols"] + [k + b": " + v for k, v in response_headers]
    return b"\r\n".join(lines) + b"\r\n\r\n"
