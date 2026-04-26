from __future__ import annotations

import asyncio
import socket
from collections.abc import Awaitable, Callable
from contextlib import suppress
from pathlib import Path
from typing import Any

from tigrcorn_security.tls import wrap_server_tls_connection
from tigrcorn_core.utils.net import ensure_parent_dir

from .base import BaseListener


class UnixListener(BaseListener):
    def __init__(self, path: str, backlog: int = 2048, ssl: Any = None, *, fd: int | None = None, sock: socket.socket | None = None) -> None:
        self.path = path
        self.backlog = backlog
        self.ssl = ssl
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
        self.sock = sock
        return sock

    async def start(self, client_connected_cb: Callable[..., Awaitable[None]]) -> None:
        path = Path(self.path) if self.path else None
        existing_sock = self._get_socket()
        if existing_sock is None and path is not None:
            ensure_parent_dir(str(path))
            if path.exists():
                path.unlink()

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

        if existing_sock is not None:
            self.server = await asyncio.start_unix_server(callback, sock=existing_sock, ssl=ssl_param, backlog=self.backlog)
        else:
            self.server = await asyncio.start_unix_server(callback, path=self.path, backlog=self.backlog, ssl=ssl_param)

    async def close(self) -> None:
        if self.server is not None:
            self.server.close()
            await self.server.wait_closed()
            self.server = None
