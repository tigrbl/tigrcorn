from __future__ import annotations

from tigrcorn_core.types import StreamReaderLike

from .body import _read_chunked_body, _readexactly
from .head import read_http11_request_head
from .models import ParsedRequest


async def read_http11_request(
    reader: StreamReaderLike,
    *,
    max_body_size: int = 16 * 1024 * 1024,
    max_header_size: int = 64 * 1024,
) -> ParsedRequest | None:
    parsed = await read_http11_request_head(
        reader,
        max_body_size=max_body_size,
        max_header_size=max_header_size,
    )
    if parsed is None:
        return None

    body = b''
    if parsed.body_kind == 'chunked':
        body = await _read_chunked_body(reader, max_body_size=max_body_size)
    elif parsed.body_kind == 'content-length':
        assert parsed.content_length is not None
        body = await _readexactly(reader, parsed.content_length)

    return ParsedRequest(
        method=parsed.method,
        target=parsed.target,
        path=parsed.path,
        raw_path=parsed.raw_path,
        query_string=parsed.query_string,
        http_version=parsed.http_version,
        headers=parsed.headers,
        body=body,
        keep_alive=parsed.keep_alive,
        expect_continue=parsed.expect_continue,
        websocket_upgrade=parsed.websocket_upgrade,
    )
