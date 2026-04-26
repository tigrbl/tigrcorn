from __future__ import annotations

import asyncio
import inspect
import socket
from collections.abc import Awaitable, Callable

from tigrcorn_transports.udp.endpoint import UDPEndpoint
from tigrcorn_transports.udp.packet import UDPPacket
from tigrcorn_transports.udp.socketopts import configure_udp_socket

from .base import BaseListener


class _UDPProtocol(asyncio.DatagramProtocol):
    def __init__(self, callback: Callable[..., Awaitable[None] | None]) -> None:
        self.callback = callback
        self.transport: asyncio.DatagramTransport | None = None
        self.endpoint: UDPEndpoint | None = None
        self.tasks: set[asyncio.Task[None]] = set()

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = transport  # runtime transport provided by asyncio
        sockname = transport.get_extra_info('sockname')
        sock = transport.get_extra_info('socket')
        if sock is not None:
            configure_udp_socket(sock)
        self.endpoint = UDPEndpoint(transport=transport, local_addr=sockname)

    def datagram_received(self, data: bytes, addr) -> None:  # type: ignore[override]
        if self.endpoint is None:
            return
        packet = UDPPacket(data=data, addr=addr)
        result = self.callback(packet, self.endpoint)
        if inspect.isawaitable(result):
            task = asyncio.create_task(result)
            self.tasks.add(task)
            task.add_done_callback(self.tasks.discard)

    def connection_lost(self, exc: Exception | None) -> None:
        for task in list(self.tasks):
            task.cancel()


class UDPListener(BaseListener):
    def __init__(self, host: str, port: int, *, reuse_port: bool = False, fd: int | None = None, sock: socket.socket | None = None) -> None:
        self.host = host
        self.port = port
        self.reuse_port = reuse_port
        self.fd = fd
        self.sock = sock
        self.transport: asyncio.DatagramTransport | None = None
        self.protocol: _UDPProtocol | None = None

    def _get_socket(self) -> socket.socket | None:
        if self.sock is not None:
            return self.sock
        if self.fd is None:
            return None
        sock = socket.socket(fileno=self.fd)
        sock.setblocking(False)
        configure_udp_socket(sock)
        self.sock = sock
        return sock

    async def start(self, client_connected_cb):
        loop = asyncio.get_running_loop()
        existing_sock = self._get_socket()
        transport, protocol = await loop.create_datagram_endpoint(
            lambda: _UDPProtocol(client_connected_cb),
            local_addr=None if existing_sock is not None else (self.host, self.port),
            reuse_port=self.reuse_port if existing_sock is None else None,
            sock=existing_sock,
        )
        self.transport = transport
        self.protocol = protocol

    async def close(self) -> None:
        if self.transport is not None:
            self.transport.close()
            self.transport = None
            self.protocol = None
