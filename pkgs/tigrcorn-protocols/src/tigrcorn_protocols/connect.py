from __future__ import annotations

import asyncio
import ipaddress
from contextlib import suppress


def parse_connect_authority(authority: str) -> tuple[str, int]:
    if authority.startswith('['):
        end = authority.find(']')
        if end == -1 or end + 2 > len(authority) or authority[end + 1] != ':':
            raise ValueError('invalid CONNECT authority-form target')
        host = authority[1:end]
        port_text = authority[end + 2:]
    else:
        if authority.count(':') != 1:
            raise ValueError('invalid CONNECT authority-form target')
        host, port_text = authority.rsplit(':', 1)
    port = int(port_text)
    if not host or port <= 0 or port > 65535:
        raise ValueError('invalid CONNECT authority-form target')
    return host, port


async def half_close_tcp_writer(writer: asyncio.StreamWriter) -> None:
    if writer.is_closing():
        return
    if writer.can_write_eof():
        with suppress(Exception):
            writer.write_eof()
            await writer.drain()
            return
    writer.close()
    with suppress(Exception):
        await writer.wait_closed()


async def close_tcp_writer(writer: asyncio.StreamWriter) -> None:
    if writer.is_closing():
        return
    writer.close()
    with suppress(Exception):
        await writer.wait_closed()



def _split_allow_entry(entry: str) -> tuple[str, str | None]:
    entry = entry.strip()
    if not entry:
        raise ValueError('empty CONNECT allowlist entry')
    if entry.startswith('['):
        if ']:' in entry:
            host, port = entry.rsplit(':', 1)
            return host[1:-1], port
        return entry[1:-1], None
    if '/' in entry:
        if entry.count(':') == 1 and entry.rsplit(':', 1)[1].isdigit():
            network, port = entry.rsplit(':', 1)
            return network, port
        return entry, None
    if entry.count(':') == 1 and entry.rsplit(':', 1)[1].isdigit():
        host, port = entry.rsplit(':', 1)
        return host, port
    return entry, None


def validate_connect_allow_entry(entry: str) -> str:
    host_or_network, port_text = _split_allow_entry(entry)
    if port_text is not None:
        port = int(port_text)
        if port <= 0 or port > 65535:
            raise ValueError('invalid CONNECT allowlist port')
    if '/' in host_or_network:
        ipaddress.ip_network(host_or_network, strict=False)
    elif not host_or_network:
        raise ValueError('empty CONNECT allowlist host')
    return entry


def is_connect_allowed(host: str, port: int, allowlist: list[str] | tuple[str, ...]) -> bool:
    if not allowlist:
        return False
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    normalized_host = host.lower()
    for raw in allowlist:
        try:
            host_or_network, port_text = _split_allow_entry(raw)
        except ValueError:
            continue
        if port_text is not None and int(port_text) != port:
            continue
        if '/' in host_or_network:
            if address is None:
                continue
            try:
                network = ipaddress.ip_network(host_or_network, strict=False)
            except ValueError:
                continue
            if address in network:
                return True
            continue
        if normalized_host == host_or_network.lower():
            return True
    return False
