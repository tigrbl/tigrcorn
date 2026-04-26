from __future__ import annotations

import gzip
import zlib
from dataclasses import dataclass

try:  # pragma: no cover - optional dependency surface
    import brotli  # type: ignore[import-not-found]
except Exception:  # pragma: no cover - optional dependency surface
    brotli = None  # type: ignore[assignment]

from tigrcorn.protocols.http1.serializer import response_allows_body
from tigrcorn.utils.headers import append_if_missing, get_header

_SUPPORTED_ENCODINGS = ('br', 'gzip', 'deflate')


def _available_supported_encodings(supported: tuple[str, ...]) -> tuple[str, ...]:
    available: list[str] = []
    for coding in supported:
        if coding == 'br' and brotli is None:
            continue
        if coding not in available:
            available.append(coding)
    return tuple(available)


@dataclass(frozen=True, slots=True)
class ContentCodingSelection:
    coding: str | None
    identity_acceptable: bool = True
    explicit_identity_forbidden: bool = False

    @property
    def not_acceptable(self) -> bool:
        return self.coding is None and not self.identity_acceptable



def _parse_qvalue(raw: str) -> float:
    try:
        value = float(raw)
    except ValueError:
        return 0.0
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value



def select_content_coding(
    request_headers: list[tuple[bytes, bytes]] | tuple[tuple[bytes, bytes], ...],
    *,
    supported: tuple[str, ...] = _SUPPORTED_ENCODINGS,
) -> ContentCodingSelection:
    supported = _available_supported_encodings(supported)
    header_value = get_header(request_headers, b'accept-encoding')
    if header_value is None:
        return ContentCodingSelection(coding=None, identity_acceptable=True)

    identity_q = 1.0
    wildcard_q: float | None = None
    coding_q: dict[str, float] = {}
    order: dict[str, int] = {}
    for index, part in enumerate(header_value.decode('ascii', 'ignore').split(',')):
        token = part.strip()
        if not token:
            continue
        name, *params = [piece.strip() for piece in token.split(';')]
        lower = name.lower()
        q = 1.0
        for param in params:
            if '=' not in param:
                continue
            key, value = param.split('=', 1)
            if key.strip().lower() == 'q':
                q = _parse_qvalue(value.strip())
        if lower == 'identity':
            identity_q = q
        elif lower == '*':
            wildcard_q = q
        else:
            coding_q[lower] = q
            order.setdefault(lower, index)

    chosen: tuple[float, int, str] | None = None
    for index, encoding in enumerate(supported):
        q = coding_q.get(encoding)
        if q is None:
            q = wildcard_q if wildcard_q is not None else 0.0
        if q <= 0.0:
            continue
        rank = (-q, order.get(encoding, 1000 + index), encoding)
        if chosen is None or rank < chosen:
            chosen = rank
    if chosen is not None:
        return ContentCodingSelection(coding=chosen[2], identity_acceptable=identity_q > 0.0, explicit_identity_forbidden=identity_q <= 0.0)
    return ContentCodingSelection(coding=None, identity_acceptable=identity_q > 0.0, explicit_identity_forbidden=identity_q <= 0.0)



def encode_content(coding: str, payload: bytes) -> bytes:
    if coding == 'gzip':
        return gzip.compress(payload)
    if coding == 'deflate':
        return zlib.compress(payload)
    if coding == 'br':
        if brotli is None:
            raise RuntimeError('brotli support is not available; install tigrcorn[compression]')
        return brotli.compress(payload)
    raise ValueError(f'unsupported content coding: {coding}')



def _replace_content_length(headers: list[tuple[bytes, bytes]], payload_length: int) -> list[tuple[bytes, bytes]]:
    filtered = [(name.lower(), value) for name, value in headers if name.lower() not in {b'content-length'}]
    filtered.append((b'content-length', str(payload_length).encode('ascii')))
    return filtered



def apply_http_content_coding(
    *,
    request_headers: list[tuple[bytes, bytes]] | tuple[tuple[bytes, bytes], ...],
    response_headers: list[tuple[bytes, bytes]],
    body: bytes,
    status: int,
    policy: str = 'allowlist',
    supported: tuple[str, ...] = _SUPPORTED_ENCODINGS,
) -> tuple[int, list[tuple[bytes, bytes]], bytes, ContentCodingSelection]:
    normalized_headers = [(bytes(name).lower(), bytes(value)) for name, value in response_headers]
    supported = _available_supported_encodings(tuple(str(item).lower() for item in supported))
    header_value = get_header(request_headers, b'accept-encoding')
    if policy == 'identity-only':
        identity_forbidden = False
        if header_value is not None:
            lowered = header_value.decode('ascii', 'ignore').lower()
            identity_forbidden = 'identity;q=0' in lowered and '*;q=0' in lowered
        selection = ContentCodingSelection(coding=None, identity_acceptable=not identity_forbidden, explicit_identity_forbidden=identity_forbidden)
    else:
        selection = select_content_coding(request_headers, supported=supported)

    if not response_allows_body(status):
        return status, normalized_headers, body, selection
    if get_header(normalized_headers, b'content-encoding') is not None:
        return status, normalized_headers, body, selection
    if not body:
        return status, normalized_headers, body, selection

    if selection.not_acceptable:
        headers = _replace_content_length([(b'content-type', b'text/plain; charset=utf-8')], len(b'not acceptable'))
        append_if_missing(headers, b'vary', b'accept-encoding')
        return 406, headers, b'not acceptable', selection

    if policy == 'strict' and header_value is not None and selection.coding is None:
        headers = _replace_content_length([(b'content-type', b'text/plain; charset=utf-8')], len(b'not acceptable'))
        append_if_missing(headers, b'vary', b'accept-encoding')
        return 406, headers, b'not acceptable', selection

    if selection.coding is None:
        return status, normalized_headers, body, selection

    encoded = encode_content(selection.coding, body)
    headers = [(name.lower(), value) for name, value in normalized_headers if name.lower() not in {b'content-length', b'content-encoding'}]
    headers.append((b'content-encoding', selection.coding.encode('ascii')))
    append_if_missing(headers, b'vary', b'accept-encoding')
    headers = _replace_content_length(headers, len(encoded))
    return status, headers, encoded, selection



__all__ = [
    'ContentCodingSelection',
    'apply_http_content_coding',
    'encode_content',
    'select_content_coding',
]
