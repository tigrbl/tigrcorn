from __future__ import annotations

import asyncio
import inspect
import logging
import socket
from collections.abc import Awaitable, Callable

from tigrcorn_transports.udp.endpoint import UDPEndpoint
from tigrcorn_transports.udp.packet import UDPPacket
from tigrcorn_transports.udp.socketopts import configure_udp_socket

from .base import BaseListener

logger = logging.getLogger("tigrcorn")


class _UDPProtocol(asyncio.DatagramProtocol):
    _PEER_STARTUP_PRIORITY_SECONDS = 4.0

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
        self._peer_priority_until: dict[tuple[str, int], float] = {}
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
        loop_time = asyncio.get_running_loop().time()
        is_long_header = bool(data and data[0] & 0x80)
        if is_long_header:
            self._peer_priority_until[addr] = (
                loop_time + self._PEER_STARTUP_PRIORITY_SECONDS
            )
        priority_until = self._peer_priority_until.get(addr, 0.0)
        if priority_until and loop_time >= priority_until:
            self._peer_priority_until.pop(addr, None)
            priority_until = 0.0
        if self._sequence % 256 == 0:
            self._peer_priority_until = {
                peer: deadline
                for peer, deadline in self._peer_priority_until.items()
                if loop_time < deadline
            }
        queue = (
            self.urgent_queue
            if is_long_header or priority_until
            else self.normal_queue
        )
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
                    # queue.get() and a lightweight callback can both finish
                    # synchronously while media keeps this queue non-empty.
                    # Yield so the reserved long-header worker can service an
                    # Initial already captured by the batched socket reader.
                    await asyncio.sleep(0)
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
            paused = False
            try:
                transport.pause_reading()
                paused = True
                reader.start()
            except (NotImplementedError, AttributeError, OSError):
                reader.sock.close()
                if paused:
                    try:
                        transport.resume_reading()
                    except (NotImplementedError, AttributeError, OSError):
                        pass
                logger.info("UDP listener using asyncio single-datagram receive path")
            else:
                self.batch_reader = reader
                logger.info(
                    "UDP listener using bounded batch receive path batch_size=%d",
                    reader._MAX_BATCH_DATAGRAMS,
                )

    async def close(self) -> None:
        if self.batch_reader is not None:
            self.batch_reader.close()
            self.batch_reader = None
        if self.transport is not None:
            self.transport.close()
            self.transport = None
            self.protocol = None
