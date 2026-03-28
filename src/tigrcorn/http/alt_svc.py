from __future__ import annotations

from collections.abc import Iterable


HeaderList = list[tuple[bytes, bytes]]


def _to_bytes(value: bytes | str) -> bytes:
    if isinstance(value, bytes):
        return value
    return str(value).encode('latin1')


def _dedupe(values: Iterable[bytes]) -> list[bytes]:
    seen: set[bytes] = set()
    result: list[bytes] = []
    for item in values:
        token = bytes(item).strip()
        if not token or token in seen:
            continue
        seen.add(token)
        result.append(token)
    return result


def configured_alt_svc_values(config, *, request_http_version: str | None = None) -> list[bytes]:
    explicit = _dedupe(_to_bytes(item) for item in getattr(config.http, 'alt_svc_headers', ()))
    if explicit:
        return explicit
    if not getattr(config.http, 'alt_svc_auto', False):
        return []
    version = str(request_http_version or '').replace('HTTP/', '').strip().lower()
    if version in {'3', '3.0', 'h3', 'http/3'}:
        return []
    values: list[bytes] = []
    max_age = int(getattr(config.http, 'alt_svc_max_age', 86400))
    persist = bool(getattr(config.http, 'alt_svc_persist', False))
    for listener in getattr(config, 'listeners', ()):  # pragma: no branch - tiny loop
        if getattr(listener, 'kind', None) != 'udp':
            continue
        enabled = set(getattr(listener, 'enabled_protocols', ()))
        if 'http3' not in enabled:
            continue
        port = getattr(listener, 'port', 0)
        if not isinstance(port, int) or port <= 0:
            continue
        fragments = [f'h3=":{port}"'.encode('ascii')]
        if max_age >= 0:
            fragments.append(f'ma={max_age}'.encode('ascii'))
        if persist:
            fragments.append(b'persist=1')
        values.append(b'; '.join(fragments))
    return _dedupe(values)


def append_alt_svc_headers(
    headers: Iterable[tuple[bytes, bytes]],
    *,
    config,
    request_http_version: str | None = None,
) -> HeaderList:
    normalized = [(bytes(name).lower(), bytes(value)) for name, value in headers]
    if any(name == b'alt-svc' for name, _value in normalized):
        return normalized
    for value in configured_alt_svc_values(config, request_http_version=request_http_version):
        normalized.append((b'alt-svc', value))
    return normalized


__all__ = ['append_alt_svc_headers', 'configured_alt_svc_values']
