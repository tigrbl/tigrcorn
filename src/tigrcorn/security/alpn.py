from __future__ import annotations

_ALLOWED_ALPN = {'http/1.1', 'h2', 'h3'}


def normalize_alpn(selected: str | None) -> str | None:
    if selected is None:
        return None
    candidate = selected.strip().lower()
    if candidate in _ALLOWED_ALPN:
        return candidate
    return candidate


def normalize_alpn_list(values: list[str] | tuple[str, ...] | None, *, for_udp: bool = False) -> list[str]:
    items = [normalize_alpn(v) for v in (values or []) if v]
    normalized = [v for v in items if v]
    if not normalized:
        normalized = ['h3'] if for_udp else ['h2', 'http/1.1']
    seen: list[str] = []
    for item in normalized:
        if item not in seen:
            seen.append(item)
    return seen


__all__ = ['normalize_alpn', 'normalize_alpn_list']
