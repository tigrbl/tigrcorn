from __future__ import annotations

from collections.abc import Iterable

from tigrcorn.utils.headers import strip_connection_specific_headers


HeaderList = list[tuple[bytes, bytes]]

# Keep the public support envelope intentionally narrow for checkpointability:
# 103 responses are treated as preload-hint carriers and only preserve Link fields.
_EARLY_HINTS_ALLOWED_HEADERS = {b'link'}


def _normalize(headers: Iterable[tuple[bytes, bytes]]) -> HeaderList:
    normalized = [(bytes(name).lower(), bytes(value)) for name, value in headers]
    return strip_connection_specific_headers(normalized)


def sanitize_informational_headers(status: int, headers: Iterable[tuple[bytes, bytes]]) -> HeaderList:
    """Return a safe informational-header list.

    For 103 Early Hints, restrict the surface to Link preload hints and drop
    connection-specific framing metadata. Other informational responses keep
    ordinary end-to-end fields except framing metadata.
    """

    normalized = _normalize(headers)
    if status == 103:
        result: HeaderList = []
        seen: set[tuple[bytes, bytes]] = set()
        for name, value in normalized:
            if name not in _EARLY_HINTS_ALLOWED_HEADERS:
                continue
            if b'\r' in value or b'\n' in value:
                continue
            item = (name, value)
            if item not in seen:
                seen.add(item)
                result.append(item)
        return result
    return [
        (name, value)
        for name, value in normalized
        if name not in {b'content-length', b'transfer-encoding'}
    ]


__all__ = ['sanitize_informational_headers']
