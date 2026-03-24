from __future__ import annotations

from dataclasses import dataclass
from ipaddress import ip_address, ip_network
from typing import Iterable, Sequence

from tigrcorn.utils.headers import get_header


@dataclass(slots=True)
class ProxyView:
    client: tuple[str, int] | None
    server: tuple[str, int] | tuple[str, None] | None
    scheme: str
    root_path: str


def _decode(value: bytes | None) -> str | None:
    if value is None:
        return None
    return value.decode('latin1', 'ignore').strip() or None


def _normalize_root_path(root_path: str) -> str:
    if not root_path:
        return ''
    root_path = root_path.strip()
    if not root_path:
        return ''
    if not root_path.startswith('/'):
        root_path = '/' + root_path
    return root_path.rstrip('/') or '/'


def _split_host_port(value: str) -> tuple[str, int | None]:
    value = value.strip().strip('"')
    if not value:
        return '', None
    if value.startswith('[') and ']:' in value:
        host, port = value.rsplit(':', 1)
        return host[1:-1], int(port)
    if value.count(':') == 1 and value.rsplit(':', 1)[1].isdigit():
        host, port = value.rsplit(':', 1)
        return host, int(port)
    return value.strip('[]'), None


def _first_csv(value: str | None) -> str | None:
    if not value:
        return None
    first = value.split(',', 1)[0].strip()
    return first or None


def _parse_forwarded(header_value: str | None) -> dict[str, str]:
    if not header_value:
        return {}
    first = header_value.split(',', 1)[0]
    result: dict[str, str] = {}
    for part in first.split(';'):
        if '=' not in part:
            continue
        key, value = part.split('=', 1)
        result[key.strip().lower()] = value.strip().strip('"')
    return result


def _client_ip(client: tuple[str, int] | None) -> str | None:
    return client[0] if client else None


def _trusted(client: tuple[str, int] | None, allowlist: Sequence[str]) -> bool:
    host = _client_ip(client)
    if host is None:
        return False
    if not allowlist:
        try:
            return ip_address(host).is_loopback
        except ValueError:
            return host in {'localhost'}
    for entry in allowlist:
        item = entry.strip()
        if not item:
            continue
        if item == '*':
            return True
        if item.lower() in {'unix', 'localhost'} and host in {'127.0.0.1', '::1', 'localhost'}:
            return True
        try:
            if '/' in item:
                if ip_address(host) in ip_network(item, strict=False):
                    return True
                continue
            if ip_address(host) == ip_address(item):
                return True
                
        except ValueError:
            if host == item:
                return True
    return False


def resolve_proxy_view(
    headers: Iterable[tuple[bytes, bytes]],
    *,
    client: tuple[str, int] | None,
    server: tuple[str, int] | tuple[str, None] | None,
    scheme: str,
    root_path: str = '',
    enabled: bool = False,
    forwarded_allow_ips: Sequence[str] = (),
) -> ProxyView:
    resolved_root = _normalize_root_path(root_path)
    view = ProxyView(client=client, server=server, scheme=scheme, root_path=resolved_root)
    if not enabled or not _trusted(client, forwarded_allow_ips):
        return view

    forwarded = _parse_forwarded(_decode(get_header(headers, b'forwarded')))
    xf_for = _first_csv(_decode(get_header(headers, b'x-forwarded-for')))
    xf_proto = _first_csv(_decode(get_header(headers, b'x-forwarded-proto')))
    xf_host = _first_csv(_decode(get_header(headers, b'x-forwarded-host')))
    xf_prefix = _first_csv(_decode(get_header(headers, b'x-forwarded-prefix')))
    x_script_name = _decode(get_header(headers, b'x-script-name'))

    forwarded_for = forwarded.get('for')
    if forwarded_for:
        host, port = _split_host_port(forwarded_for)
        if host:
            view.client = (host, port or (client[1] if client else 0))
    elif xf_for:
        host, port = _split_host_port(xf_for)
        if host:
            view.client = (host, port or (client[1] if client else 0))

    forwarded_proto = forwarded.get('proto')
    if forwarded_proto:
        view.scheme = forwarded_proto
    elif xf_proto:
        view.scheme = xf_proto

    forwarded_host = forwarded.get('host')
    host_value = forwarded_host or xf_host
    if host_value:
        host, port = _split_host_port(host_value)
        if host:
            current_port = server[1] if server else None
            view.server = (host, port if port is not None else current_port)

    prefix = forwarded.get('path') or xf_prefix or x_script_name
    if prefix:
        normalized = _normalize_root_path(prefix)
        if view.root_path and normalized and normalized != view.root_path:
            combined = _normalize_root_path(view.root_path + '/' + normalized.lstrip('/'))
            view.root_path = combined
        else:
            view.root_path = normalized or view.root_path
    return view


def strip_root_path(path: str, raw_path: bytes, root_path: str) -> tuple[str, bytes]:
    normalized = _normalize_root_path(root_path)
    if not normalized or normalized == '/':
        return path, raw_path
    if path == normalized:
        return '/', b'/'
    if path.startswith(normalized + '/'):
        stripped_path = path[len(normalized):] or '/'
        stripped_raw = raw_path[len(normalized.encode('latin1')):] or b'/'
        return stripped_path, stripped_raw
    return path, raw_path
