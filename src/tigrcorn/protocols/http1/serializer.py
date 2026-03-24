from __future__ import annotations

from tigrcorn.utils.headers import append_if_missing, get_header


_REASON_PHRASES = {
    100: b"Continue",
    101: b"Switching Protocols",
    103: b"Early Hints",
    200: b"OK",
    201: b"Created",
    202: b"Accepted",
    204: b"No Content",
    301: b"Moved Permanently",
    302: b"Found",
    304: b"Not Modified",
    400: b"Bad Request",
    401: b"Unauthorized",
    403: b"Forbidden",
    404: b"Not Found",
    405: b"Method Not Allowed",
    413: b"Payload Too Large",
    426: b"Upgrade Required",
    500: b"Internal Server Error",
    503: b"Service Unavailable",
}


def _reason(status: int) -> bytes:
    return _REASON_PHRASES.get(status, b"OK")



def response_allows_body(status: int) -> bool:
    return not (100 <= status < 200 or status in {204, 304})



def response_allows_implicit_content_length(status: int) -> bool:
    return response_allows_body(status)



def _normalize_response_headers(
    *,
    status: int,
    headers: list[tuple[bytes, bytes]],
    keep_alive: bool,
    server_header: bytes | None,
    chunked: bool,
) -> list[tuple[bytes, bytes]]:
    normalized = [(k.lower(), v) for k, v in headers]
    if server_header:
        append_if_missing(normalized, b"server", server_header)
    append_if_missing(normalized, b"connection", b"keep-alive" if keep_alive else b"close")

    if not response_allows_body(status):
        normalized = [(k, v) for k, v in normalized if k != b"transfer-encoding"]
        if 100 <= status < 200 or status == 204:
            normalized = [(k, v) for k, v in normalized if k != b"content-length"]
        return normalized

    if chunked and get_header(normalized, b"transfer-encoding") is None and get_header(normalized, b"content-length") is None:
        normalized.append((b"transfer-encoding", b"chunked"))
    return normalized



def serialize_http11_response_head(
    *,
    status: int,
    headers: list[tuple[bytes, bytes]],
    keep_alive: bool,
    server_header: bytes | None = None,
    chunked: bool = False,
) -> bytes:
    normalized = _normalize_response_headers(
        status=status,
        headers=headers,
        keep_alive=keep_alive,
        server_header=server_header,
        chunked=chunked,
    )
    status_line = b"HTTP/1.1 " + str(status).encode("ascii") + b" " + _reason(status)
    lines = [status_line] + [k + b": " + v for k, v in normalized]
    return b"\r\n".join(lines) + b"\r\n\r\n"



def serialize_http11_response_whole(
    *,
    status: int,
    headers: list[tuple[bytes, bytes]],
    body: bytes,
    keep_alive: bool,
    server_header: bytes | None = None,
) -> bytes:
    normalized = [(k.lower(), v) for k, v in headers]
    payload = body if response_allows_body(status) else b""
    if response_allows_implicit_content_length(status) and get_header(normalized, b"content-length") is None:
        normalized.append((b"content-length", str(len(payload)).encode("ascii")))
    head = serialize_http11_response_head(
        status=status,
        headers=normalized,
        keep_alive=keep_alive,
        server_header=server_header,
        chunked=False,
    )
    return head + payload



def serialize_http11_response_chunk(chunk: bytes) -> bytes:
    return f"{len(chunk):X}".encode("ascii") + b"\r\n" + chunk + b"\r\n"



def finalize_chunked_body(trailers: list[tuple[bytes, bytes]] | None = None) -> bytes:
    if not trailers:
        return b"0\r\n\r\n"
    lines = [b"0"] + [bytes(name) + b": " + bytes(value) for name, value in trailers]
    return b"\r\n".join(lines) + b"\r\n\r\n"
