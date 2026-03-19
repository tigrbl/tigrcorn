from __future__ import annotations

import asyncio
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
