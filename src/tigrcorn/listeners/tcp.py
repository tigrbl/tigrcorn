from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import Any

from tigrcorn.security.tls import wrap_server_tls_connection
from tigrcorn.transports.tcp.socketopts import configure_socket

from .base import BaseListener


class TCPListener(BaseListener):
    def __init__(self, host: str, port: int, backlog: int = 2048, ssl: Any = None, *, reuse_port: bool = False) -> None:
        self.host = host
        self.port = port
        self.backlog = backlog
        self.ssl = ssl
        self.reuse_port = reuse_port
        self.server: asyncio.AbstractServer | None = None

    async def start(self, client_connected_cb: Callable[..., Awaitable[None]]) -> None:
        ssl_param = None
        if self.ssl is None:
            callback = client_connected_cb
        elif hasattr(self.ssl, 'certificate_pem') and hasattr(self.ssl, 'private_key_pem'):
            async def callback(raw_reader: asyncio.StreamReader, raw_writer: asyncio.StreamWriter) -> None:
                try:
                    connection = await wrap_server_tls_connection(raw_reader, raw_writer, self.ssl)
                except Exception:
                    raw_writer.close()
                    with suppress(Exception):
                        await raw_writer.wait_closed()
                    return
                await client_connected_cb(connection, connection)
        else:
            callback = client_connected_cb
            ssl_param = self.ssl

        self.server = await asyncio.start_server(
            callback,
            host=self.host,
            port=self.port,
            backlog=self.backlog,
            ssl=ssl_param,
            reuse_port=self.reuse_port,
        )
        sockets = self.server.sockets or []
        for sock in sockets:
            configure_socket(sock)

    async def close(self) -> None:
        if self.server is not None:
            self.server.close()
            await self.server.wait_closed()
