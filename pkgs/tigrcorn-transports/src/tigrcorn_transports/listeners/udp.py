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
    _NORMAL_DISPATCH_QUANTUM_SECONDS = 0.001

    def __init__(
        self,
        callback: Callable[..., Awaitable[None] | None],
        *,
        dispatch_workers: int = 4,
    ) -> None:
        self.callback = callback
        # One worker is reserved for QUIC long-header traffic.  A minimum of
        # two workers ensures bulk media can never occupy the handshake lane.
        self.dispatch_workers = max(2, dispatch_workers)
        self.transport: asyncio.DatagramTransport | None = None
        self.endpoint: UDPEndpoint | None = None
        self.tasks: set[asyncio.Task[None]] = set()
        self.urgent_queue: asyncio.Queue[tuple[int, UDPPacket]] = asyncio.Queue()
        self.normal_queue: asyncio.Queue[tuple[int, UDPPacket]] = asyncio.Queue()
        self._sequence = 0

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = transport  # runtime transport provided by asyncio
        sockname = transport.get_extra_info("sockname")
        sock = transport.get_extra_info("socket")
        if sock is not None:
            configure_udp_socket(sock)
        self.endpoint = UDPEndpoint(transport=transport, local_addr=sockname)
        queues = [
            self.urgent_queue,
            *([self.normal_queue] * (self.dispatch_workers - 1)),
        ]
        for index, queue in enumerate(queues):
            task = asyncio.create_task(
                self._dispatch(queue, urgent=queue is self.urgent_queue),
                name=f"tigrcorn-udp-dispatch-{index}",
            )
            self.tasks.add(task)
            task.add_done_callback(self.tasks.discard)

    def datagram_received(self, data: bytes, addr) -> None:  # type: ignore[override]
        if self.endpoint is None:
            return
        packet = UDPPacket(data=data, addr=addr)
        self._sequence += 1
        queue = self.urgent_queue if data and data[0] & 0x80 else self.normal_queue
        queue.put_nowait((self._sequence, packet))

    async def _dispatch(
        self,
        queue: asyncio.Queue[tuple[int, UDPPacket]],
        *,
        urgent: bool,
    ) -> None:
        while True:
            _sequence, packet = await queue.get()
            try:
                if not urgent:
                    # Selector datagram transports read one packet per ready
                    # callback.  Yield a small I/O quantum before bulk work so
                    # an Initial behind media in the kernel queue is discovered
                    # before Chromium's four-second opening deadline.
                    await asyncio.sleep(self._NORMAL_DISPATCH_QUANTUM_SECONDS)
                if self.endpoint is None:
                    continue
                result = self.callback(packet, self.endpoint)
                if inspect.isawaitable(result):
                    await result
            except asyncio.CancelledError:
                raise
            # A bad application callback must not permanently reduce the fixed
            # dispatcher pool or stop later QUIC handshakes from being served.
            except Exception as exc:  # noqa: BLE001
                asyncio.get_running_loop().call_exception_handler(
                    {
                        "message": "Tigrcorn UDP datagram callback failed",
                        "exception": exc,
                        "protocol": self,
                    }
                )
            finally:
                queue.task_done()

    def connection_lost(self, exc: Exception | None) -> None:
        for task in list(self.tasks):
            task.cancel()


class UDPListener(BaseListener):
    def __init__(
        self,
        host: str,
        port: int,
        *,
        reuse_port: bool = False,
        fd: int | None = None,
        sock: socket.socket | None = None,
    ) -> None:
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
