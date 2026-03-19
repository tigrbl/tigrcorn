from __future__ import annotations

import asyncio
import unittest

from tigrcorn.scheduler import ProductionScheduler, SchedulerPolicy


class ProductionSchedulerTests(unittest.IsolatedAsyncioTestCase):
    async def test_connection_leases_and_task_tracking(self) -> None:
        scheduler = ProductionScheduler(SchedulerPolicy(max_connections=1, max_tasks=2))
        lease = scheduler.acquire_connection()
        self.assertIsNotNone(lease)
        self.assertEqual(scheduler.open_connections, 1)
        self.assertIsNone(scheduler.acquire_connection())

        seen: list[int] = []

        async def job(value: int) -> None:
            await asyncio.sleep(0)
            seen.append(value)

        first = scheduler.spawn(job(1), owner='alpha')
        second = scheduler.spawn(job(2), owner='beta')
        await asyncio.gather(first, second)
        self.assertEqual(seen, [1, 2])
        self.assertEqual(scheduler.active_tasks, 0)

        lease.release()
        self.assertEqual(scheduler.open_connections, 0)
        await scheduler.close()
        self.assertTrue(scheduler.closed)

    async def test_scheduler_rejects_spawn_after_close(self) -> None:
        scheduler = ProductionScheduler(SchedulerPolicy(max_tasks=1))
        await scheduler.close()
        with self.assertRaises(RuntimeError):
            scheduler.spawn(asyncio.sleep(0))
