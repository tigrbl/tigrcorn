from __future__ import annotations

import asyncio

from tigrcorn_transports.listeners.udp import _UDPProtocol


class _Transport:
    def get_extra_info(self, name: str):
        if name == "sockname":
            return ("127.0.0.1", 4433)
        return None


def test_udp_dispatch_reserves_a_worker_for_quic_long_headers() -> None:
    asyncio.run(_priority_case())


async def _priority_case() -> None:
    release_media = asyncio.Event()
    all_media_started = asyncio.Event()
    initial_started = asyncio.Event()
    started: list[bytes] = []

    async def callback(packet, _endpoint) -> None:
        started.append(packet.data)
        if packet.data.startswith(b"media"):
            if len([item for item in started if item.startswith(b"media")]) == 3:
                all_media_started.set()
            await release_media.wait()
        elif packet.data == b"\xc0new-initial":
            initial_started.set()

    protocol = _UDPProtocol(callback, dispatch_workers=4)
    protocol.connection_made(_Transport())  # type: ignore[arg-type]
    try:
        for index in range(4):
            protocol.datagram_received(f"media-{index}".encode(), ("127.0.0.1", 50000))
        await asyncio.wait_for(all_media_started.wait(), timeout=0.2)
        protocol.datagram_received(b"\xc0new-initial", ("127.0.0.1", 50001))

        await asyncio.wait_for(initial_started.wait(), timeout=0.2)
        assert b"media-3" not in started
        release_media.set()
        await asyncio.wait_for(protocol.urgent_queue.join(), timeout=0.2)
        await asyncio.wait_for(protocol.normal_queue.join(), timeout=0.2)

        assert started.index(b"\xc0new-initial") < started.index(b"media-3")
    finally:
        protocol.connection_lost(None)


def test_udp_dispatch_uses_a_bounded_worker_set() -> None:
    asyncio.run(_bounded_worker_case())


async def _bounded_worker_case() -> None:
    release = asyncio.Event()

    async def callback(_packet, _endpoint) -> None:
        await release.wait()

    protocol = _UDPProtocol(callback, dispatch_workers=2)
    protocol.connection_made(_Transport())  # type: ignore[arg-type]
    try:
        for index in range(20):
            protocol.datagram_received(bytes([index]), ("127.0.0.1", 50000))
        await asyncio.sleep(0)

        assert len(protocol.tasks) == 2
        assert protocol.urgent_queue.qsize() == 0
        assert protocol.normal_queue.qsize() == 19
    finally:
        release.set()
        protocol.connection_lost(None)


def test_udp_dispatch_gives_ingress_an_io_quantum_before_media_work() -> None:
    asyncio.run(_ingress_quantum_case())


async def _ingress_quantum_case() -> None:
    media_started = asyncio.Event()

    async def callback(_packet, _endpoint) -> None:
        media_started.set()

    protocol = _UDPProtocol(callback, dispatch_workers=2)
    protocol.connection_made(_Transport())  # type: ignore[arg-type]
    try:
        protocol.datagram_received(b"media", ("127.0.0.1", 50000))
        await asyncio.sleep(0)
        assert not media_started.is_set()
        await asyncio.wait_for(media_started.wait(), timeout=0.2)
    finally:
        protocol.connection_lost(None)
