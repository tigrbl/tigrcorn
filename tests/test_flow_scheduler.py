import asyncio
import unittest

from tigrcorn.flow.backpressure import BackpressureState
from tigrcorn.flow.credits import CreditWindow
from tigrcorn.flow.keepalive import KeepAlivePolicy
from tigrcorn.flow.timeouts import TimeoutPolicy
from tigrcorn.flow.watermarks import Watermarks
from tigrcorn.scheduler.cancellation import cancel, cancel_many
from tigrcorn.scheduler.dispatch import TaskDispatcher
from tigrcorn.scheduler.policy import SchedulerPolicy
from tigrcorn.scheduler.quotas import Quotas
from tigrcorn.scheduler.tasks import TaskSet


class FlowSchedulerTests(unittest.IsolatedAsyncioTestCase):
    async def test_dispatcher_and_taskset(self):
        dispatcher = TaskDispatcher(SchedulerPolicy(max_tasks=2))
        seen = []

        async def job(x):
            seen.append(x)

        t1 = dispatcher.spawn(job(1))
        t2 = dispatcher.spawn(job(2))
        with self.assertRaises(RuntimeError):
            dispatcher.spawn(job(3))
        await asyncio.gather(t1, t2)
        self.assertEqual(seen, [1, 2])

        taskset = TaskSet()
        sleeper = asyncio.create_task(asyncio.sleep(10))
        taskset.add(sleeper)
        await taskset.cancel_all()
        self.assertTrue(sleeper.cancelled())

    async def test_cancellation_helpers(self):
        task = asyncio.create_task(asyncio.sleep(10))
        await cancel(task)
        self.assertTrue(task.cancelled())
        tasks = [asyncio.create_task(asyncio.sleep(10)) for _ in range(2)]
        await cancel_many(tasks)
        self.assertTrue(all(task.cancelled() for task in tasks))

    async def test_timeout_policy(self):
        policy = TimeoutPolicy(read_timeout=0.1, write_timeout=0.1)
        result = await policy.wait_read(asyncio.sleep(0, result=5))
        self.assertEqual(result, 5)
        with self.assertRaises(asyncio.TimeoutError):
            await policy.wait_write(asyncio.sleep(1))

    def test_backpressure_watermarks_credits_keepalive_quotas(self):
        bp = BackpressureState(high_water=10, low_water=3)
        self.assertFalse(bp.update(2))
        self.assertTrue(bp.update(10))
        self.assertFalse(bp.update(3))
        watermarks = Watermarks(low=2, high=5)
        self.assertEqual(watermarks.classify(1), 'low')
        self.assertEqual(watermarks.classify(3), 'mid')
        self.assertEqual(watermarks.classify(5), 'high')
        credits = CreditWindow(remaining=5)
        credits.consume(3)
        self.assertTrue(credits.available(2))
        credits.refill(4)
        self.assertEqual(credits.remaining, 6)
        keepalive = KeepAlivePolicy(idle_timeout=10, ping_interval=5)
        self.assertTrue(keepalive.should_ping(0, now=6))
        self.assertTrue(keepalive.expired(0, now=11))
        quotas = Quotas(max_connections=1)
        self.assertTrue(quotas.acquire_connection())
        self.assertFalse(quotas.acquire_connection())
        quotas.release_connection()
        self.assertTrue(quotas.acquire_connection())
