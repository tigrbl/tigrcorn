from __future__ import annotations

import asyncio

import pytest

from tigrcorn.scheduler import ProductionScheduler, SchedulerPolicy


@pytest.mark.asyncio
async def test_connection_leases_and_task_tracking() -> None:
    scheduler = ProductionScheduler(SchedulerPolicy(max_connections=1, max_tasks=2))
    lease = scheduler.acquire_connection()
    assert lease is not None
    assert scheduler.open_connections == 1
    assert scheduler.acquire_connection() is None

    seen: list[int] = []

    async def job(value: int) -> None:
        await asyncio.sleep(0)
        seen.append(value)

    first = scheduler.spawn(job(1), owner="alpha")
    second = scheduler.spawn(job(2), owner="beta")
    await asyncio.gather(first, second)
    assert seen == [1, 2]
    assert scheduler.active_tasks == 0

    lease.release()
    assert scheduler.open_connections == 0
    await scheduler.close()
    assert scheduler.closed


@pytest.mark.asyncio
async def test_scheduler_rejects_spawn_after_close() -> None:
    scheduler = ProductionScheduler(SchedulerPolicy(max_tasks=1))
    await scheduler.close()
    with pytest.raises(RuntimeError):
        scheduler.spawn(asyncio.sleep(0))
