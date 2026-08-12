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
                self._dispatch(queue),
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

    async def _dispatch(self, queue: asyncio.Queue[tuple[int, UDPPacket]]) -> None:
        while True:
            _sequence, packet = await queue.get()
            try:
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


class _BatchedUDPReader:
    """Drain multiple queued datagrams per selector readiness callback."""

    _MAX_BATCH_DATAGRAMS = 256

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        protocol: _UDPProtocol,
        sock: socket.socket,
    ) -> None:
        self.loop = loop
        self.protocol = protocol
        self.sock = sock

    def start(self) -> None:
        self.loop.add_reader(self.sock.fileno(), self._read_ready)

    def _read_ready(self) -> None:
        for _ in range(self._MAX_BATCH_DATAGRAMS):
            try:
                data, addr = self.sock.recvfrom(65536)
            except (BlockingIOError, InterruptedError):
                return
            except OSError as exc:
                self.loop.call_exception_handler(
                    {
                        "message": "Tigrcorn UDP batch receive failed",
                        "exception": exc,
                    }
                )
                return
            self.protocol.datagram_received(data, addr)

    def close(self) -> None:
        self.loop.remove_reader(self.sock.fileno())
        self.sock.close()


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
        self.batch_reader: _BatchedUDPReader | None = None

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
        transport_socket = transport.get_extra_info("socket")
        if transport_socket is not None and hasattr(transport, "pause_reading"):
            duplicate = transport_socket.dup()
            duplicate.setblocking(False)
            reader = _BatchedUDPReader(loop, protocol, duplicate)
            try:
                transport.pause_reading()
                reader.start()
            except (NotImplementedError, AttributeError, OSError):
                reader.sock.close()
                transport.resume_reading()
            else:
                self.batch_reader = reader

    async def close(self) -> None:
        if self.batch_reader is not None:
            self.batch_reader.close()
            self.batch_reader = None
        if self.transport is not None:
            self.transport.close()
            self.transport = None
            self.protocol = None
