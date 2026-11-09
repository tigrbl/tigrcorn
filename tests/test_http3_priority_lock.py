from __future__ import annotations

import asyncio

from tigrcorn_protocols.http3.handler.priority_lock import PriorityLock


def test_urgent_waiter_precedes_queued_normal_work() -> None:
    async def exercise() -> list[str]:
        lock = PriorityLock()
        order: list[str] = []
        release_owner = asyncio.Event()

        async def owner() -> None:
            async with lock:
                order.append("owner")
                await release_owner.wait()

        async def normal() -> None:
            async with lock:
                order.append("normal")

        async def urgent() -> None:
            async with lock.urgent():
                order.append("urgent")

        owner_task = asyncio.create_task(owner())
        await asyncio.sleep(0)
        normal_task = asyncio.create_task(normal())
        await asyncio.sleep(0)
        urgent_task = asyncio.create_task(urgent())
        await asyncio.sleep(0)
        release_owner.set()
        await asyncio.gather(owner_task, normal_task, urgent_task)
        return order

    assert asyncio.run(exercise()) == ["owner", "urgent", "normal"]


def test_cancelled_urgent_waiter_does_not_wedge_lock() -> None:
    async def exercise() -> bool:
        lock = PriorityLock()
        await lock.acquire()
        waiter = asyncio.create_task(lock.acquire(urgent=True))
        await asyncio.sleep(0)
        waiter.cancel()
        try:
            await waiter
        except asyncio.CancelledError:
            pass
        lock.release()
        async with lock:
            return True

    assert asyncio.run(exercise()) is True


def test_handoff_releases_registry_before_waiting_for_session() -> None:
    async def exercise() -> list[str]:
        registry = PriorityLock()
        busy_session = PriorityLock()
        order: list[str] = []
        release_session = asyncio.Event()

        async def media_owner() -> None:
            async with busy_session:
                order.append("media")
                await release_session.wait()

        async def blocked_packet() -> None:
            async with registry.normal() as packet_lock:
                order.append("routed")
                await packet_lock.handoff(busy_session)
                order.append("same-session")

        async def new_handshake() -> None:
            async with registry.urgent():
                order.append("new-handshake")

        media_task = asyncio.create_task(media_owner())
        await asyncio.sleep(0)
        blocked_task = asyncio.create_task(blocked_packet())
        await asyncio.sleep(0)
        handshake_task = asyncio.create_task(new_handshake())
        await asyncio.sleep(0)
        release_session.set()
        await asyncio.gather(media_task, blocked_task, handshake_task)
        return order

    assert asyncio.run(exercise()) == [
        "media",
        "routed",
        "new-handshake",
        "same-session",
    ]


def test_cancelled_handoff_does_not_release_another_sessions_owner() -> None:
    async def exercise() -> bool:
        registry = PriorityLock()
        session = PriorityLock()
        await session.acquire()

        async def blocked_handoff() -> None:
            async with registry.normal() as packet_lock:
                await packet_lock.handoff(session)

        task = asyncio.create_task(blocked_handoff())
        await asyncio.sleep(0)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        session.release()
        async with session:
            return True

    assert asyncio.run(exercise()) is True
