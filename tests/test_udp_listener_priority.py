from __future__ import annotations

import asyncio

from tigrcorn_transports.listeners.udp import _UDPProtocol


class _Transport:
    def get_extra_info(self, name: str):
        if name == "sockname":
            return ("127.0.0.1", 4433)
        return None


def test_udp_dispatch_prioritizes_quic_long_headers_over_queued_media() -> None:
    asyncio.run(_priority_case())


async def _priority_case() -> None:
    release_media = asyncio.Event()
    first_media_started = asyncio.Event()
    started: list[bytes] = []

    async def callback(packet, _endpoint) -> None:
        started.append(packet.data)
        if packet.data == b"first-media":
            first_media_started.set()
            await release_media.wait()

    protocol = _UDPProtocol(callback, dispatch_workers=1)
    protocol.connection_made(_Transport())  # type: ignore[arg-type]
    try:
        protocol.datagram_received(b"first-media", ("127.0.0.1", 50000))
        await asyncio.wait_for(first_media_started.wait(), timeout=0.2)
        protocol.datagram_received(b"queued-media", ("127.0.0.1", 50000))
        protocol.datagram_received(b"\xc0new-initial", ("127.0.0.1", 50001))

        release_media.set()
        await asyncio.wait_for(protocol.queue.join(), timeout=0.2)

        assert started == [b"first-media", b"\xc0new-initial", b"queued-media"]
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
        assert protocol.queue.qsize() == 18
    finally:
        release.set()
        protocol.connection_lost(None)
