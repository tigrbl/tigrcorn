from __future__ import annotations

from tigrcorn_core.utils.headers import apply_response_header_policy, get_header, sanitize_early_hints_headers, strip_connection_specific_headers


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
    421: b"Misdirected Request",
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
    include_date_header: bool,
    default_headers: list[tuple[bytes, bytes]] | None,
    alt_svc_values: list[bytes] | None,
) -> list[tuple[bytes, bytes]]:
    if 100 <= status < 200:
        if status == 103:
            return sanitize_early_hints_headers(headers)
        return [(bytes(k).lower(), bytes(v)) for k, v in strip_connection_specific_headers(headers)]

    normalized = apply_response_header_policy(
        headers,
        server_header=server_header,
        include_date_header=include_date_header,
        default_headers=default_headers or (),
        alt_svc_values=alt_svc_values or (),
    )
    if get_header(normalized, b'connection') is None:
        normalized.append((b'connection', b'keep-alive' if keep_alive else b'close'))

    if not response_allows_body(status):
        normalized = [(k, v) for k, v in normalized if k != b'transfer-encoding']
        if status == 204:
            normalized = [(k, v) for k, v in normalized if k != b'content-length']
        return normalized

    if chunked and get_header(normalized, b'transfer-encoding') is None and get_header(normalized, b'content-length') is None:
        normalized.append((b'transfer-encoding', b'chunked'))
    return normalized



HTTP11_RESPONSE_METADATA_RULES: tuple[dict[str, object], ...] = (
    {
        'selector': '1xx',
        'allows_body': False,
        'allows_transfer_encoding': False,
        'allows_content_length': False,
        'implicit_content_length': False,
        'notes': 'informational responses never carry a final response body',
    },
    {
        'selector': '204',
        'allows_body': False,
        'allows_transfer_encoding': False,
        'allows_content_length': False,
        'implicit_content_length': False,
        'notes': '204 response body is always empty',
    },
    {
        'selector': '304',
        'allows_body': False,
        'allows_transfer_encoding': False,
        'allows_content_length': True,
        'implicit_content_length': False,
        'notes': '304 is bodyless but may carry representation metadata',
    },
    {
        'selector': 'other-final',
        'allows_body': True,
        'allows_transfer_encoding': True,
        'allows_content_length': True,
        'implicit_content_length': True,
        'notes': 'non-bodyless final responses may receive implicit Content-Length when fully buffered',
    },
)


def http11_response_metadata_rules() -> tuple[dict[str, object], ...]:
    return tuple(dict(entry) for entry in HTTP11_RESPONSE_METADATA_RULES)


def serialize_http11_response_head(
    *,
    status: int,
    headers: list[tuple[bytes, bytes]],
    keep_alive: bool,
    server_header: bytes | None = None,
    chunked: bool = False,
    include_date_header: bool = True,
    default_headers: list[tuple[bytes, bytes]] | None = None,
    alt_svc_values: list[bytes] | None = None,
) -> bytes:
    normalized = _normalize_response_headers(
        status=status,
        headers=headers,
        keep_alive=keep_alive,
        server_header=server_header,
        chunked=chunked,
        include_date_header=include_date_header,
        default_headers=default_headers,
        alt_svc_values=alt_svc_values,
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
    include_date_header: bool = True,
    default_headers: list[tuple[bytes, bytes]] | None = None,
    alt_svc_values: list[bytes] | None = None,
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
        include_date_header=include_date_header,
        default_headers=default_headers,
        alt_svc_values=alt_svc_values,
    )
    return head + payload



def serialize_http11_response_chunk(chunk: bytes) -> bytes:
    return f"{len(chunk):X}".encode("ascii") + b"\r\n" + chunk + b"\r\n"



def finalize_chunked_body(trailers: list[tuple[bytes, bytes]] | None = None) -> bytes:
    if not trailers:
        return b"0\r\n\r\n"
    lines = [b"0"] + [bytes(name) + b": " + bytes(value) for name, value in trailers]
    return b"\r\n".join(lines) + b"\r\n\r\n"
