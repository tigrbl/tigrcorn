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
