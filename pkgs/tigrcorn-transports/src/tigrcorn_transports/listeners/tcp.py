from __future__ import annotations

import asyncio
import socket
from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import Any

from tigrcorn.security.tls import wrap_server_tls_connection
from tigrcorn.transports.tcp.socketopts import configure_socket

from .base import BaseListener


class TCPListener(BaseListener):
    def __init__(
        self,
        host: str,
        port: int,
        backlog: int = 2048,
        ssl: Any = None,
        *,
        reuse_port: bool = False,
        reuse_address: bool = True,
        nodelay: bool = True,
        fd: int | None = None,
        sock: socket.socket | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.backlog = backlog
        self.ssl = ssl
        self.reuse_port = reuse_port
        self.reuse_address = reuse_address
        self.nodelay = nodelay
        self.fd = fd
        self.sock = sock
        self.server: asyncio.AbstractServer | None = None

    def _get_socket(self) -> socket.socket | None:
        if self.sock is not None:
            return self.sock
        if self.fd is None:
            return None
        sock = socket.socket(fileno=self.fd)
        sock.setblocking(False)
        configure_socket(sock, nodelay=self.nodelay)
        self.sock = sock
        return sock

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

        existing_sock = self._get_socket()
        if existing_sock is not None:
            self.server = await asyncio.start_server(callback, sock=existing_sock, ssl=ssl_param, backlog=self.backlog)
        else:
            self.server = await asyncio.start_server(
                callback,
                host=self.host,
                port=self.port,
                backlog=self.backlog,
                ssl=ssl_param,
                reuse_port=self.reuse_port,
                reuse_address=self.reuse_address,
            )
        sockets = self.server.sockets or []
        for sock in sockets:
            configure_socket(sock, nodelay=self.nodelay)

    async def close(self) -> None:
        if self.server is not None:
            self.server.close()
            await self.server.wait_closed()
            self.server = None
