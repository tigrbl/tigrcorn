from __future__ import annotations

import gzip
import zlib
from typing import Any

try:  # pragma: no cover - optional dependency surface
    import brotli  # type: ignore[import-not-found]
except Exception:  # pragma: no cover - optional dependency surface
    brotli = None  # type: ignore[assignment]


def header_map(headers: list[tuple[str, str]] | list[list[str]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for name, value in headers:
        result[str(name).lower()] = str(value)
    return result


def decode_response_body(headers: list[tuple[str, str]] | list[list[str]], body: bytes) -> dict[str, Any]:
    mapping = header_map(headers)
    content_encoding = mapping.get('content-encoding')
    vary = mapping.get('vary')
    decoded = body
    if content_encoding == 'gzip':
        decoded = gzip.decompress(body)
    elif content_encoding == 'deflate':
        decoded = zlib.decompress(body)
    elif content_encoding == 'br':
        if brotli is None:
            raise RuntimeError('brotli is not available')
        decoded = brotli.decompress(body)
    return {
        'content_encoding': content_encoding,
        'vary': vary,
        'decoded_body': decoded.decode('utf-8', errors='replace'),
        'encoded_length': len(body),
        'decoded_length': len(decoded),
    }
