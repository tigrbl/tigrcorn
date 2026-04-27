from __future__ import annotations

from typing import Iterable


def split_authority(value: bytes | str | None) -> tuple[str, int | None]:
    if value is None:
        return '', None
    if isinstance(value, bytes):
        value = value.decode('latin1', 'ignore')
    raw = value.strip()
    if not raw:
        return '', None
    if raw.startswith('['):
        if ']:' in raw:
            host, port = raw.rsplit(':', 1)
            return host[1:-1].lower(), int(port)
        return raw.strip('[]').lower(), None
    if raw.count(':') == 1:
        host, port = raw.rsplit(':', 1)
        if port.isdigit():
            return host.lower(), int(port)
    return raw.lower(), None


def authority_allowed(authority: bytes | str | None, allowlist: Iterable[str]) -> bool:
    entries = [entry.strip().lower() for entry in allowlist if entry and entry.strip()]
    if not entries:
        return True
    host, port = split_authority(authority)
    if not host:
        return False
    full = f'{host}:{port}' if port is not None else host
    for entry in entries:
        if entry == '*':
            return True
        allowed_host, allowed_port = split_authority(entry)
        if allowed_host.startswith('*.'):
            suffix = allowed_host[1:]
            if host.endswith(suffix) and host != suffix[1:]:
                if allowed_port is None or allowed_port == port:
                    return True
            continue
        if allowed_host.startswith('.'):
            suffix = allowed_host
            if host.endswith(suffix) and host != suffix[1:]:
                if allowed_port is None or allowed_port == port:
                    return True
            continue
        if allowed_port is not None:
            if full == f'{allowed_host}:{allowed_port}':
                return True
        elif host == allowed_host:
            return True
    return False
