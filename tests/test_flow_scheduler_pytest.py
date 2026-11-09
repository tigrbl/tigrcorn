import asyncio

import pytest

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


@pytest.mark.asyncio
async def test_dispatcher_and_taskset() -> None:
    dispatcher = TaskDispatcher(SchedulerPolicy(max_tasks=2))
    seen = []

    async def job(x):
        seen.append(x)

    t1 = dispatcher.spawn(job(1))
    t2 = dispatcher.spawn(job(2))
    with pytest.raises(RuntimeError):
        dispatcher.spawn(job(3))
    await asyncio.gather(t1, t2)
    assert seen == [1, 2]

    taskset = TaskSet()
    sleeper = asyncio.create_task(asyncio.sleep(10))
    taskset.add(sleeper)
    await taskset.cancel_all()
    assert sleeper.cancelled()


@pytest.mark.asyncio
async def test_cancellation_helpers() -> None:
    task = asyncio.create_task(asyncio.sleep(10))
    await cancel(task)
    assert task.cancelled()
    tasks = [asyncio.create_task(asyncio.sleep(10)) for _ in range(2)]
    await cancel_many(tasks)
    assert all(task.cancelled() for task in tasks)


@pytest.mark.asyncio
async def test_timeout_policy() -> None:
    policy = TimeoutPolicy(read_timeout=0.1, write_timeout=0.1)
    result = await policy.wait_read(asyncio.sleep(0, result=5))
    assert result == 5
    with pytest.raises(asyncio.TimeoutError):
        await policy.wait_write(asyncio.sleep(1))


def test_backpressure_watermarks_credits_keepalive_quotas() -> None:
    bp = BackpressureState(high_water=10, low_water=3)
    assert not bp.update(2)
    assert bp.update(10)
    assert not bp.update(3)
    watermarks = Watermarks(low=2, high=5)
    assert watermarks.classify(1) == "low"
    assert watermarks.classify(3) == "mid"
    assert watermarks.classify(5) == "high"
    credits = CreditWindow(remaining=5)
    credits.consume(3)
    assert credits.available(2)
    credits.refill(4)
    assert credits.remaining == 6
    keepalive = KeepAlivePolicy(idle_timeout=10, ping_interval=5)
    assert keepalive.should_ping(0, now=6)
    assert keepalive.expired(0, now=11)
    quotas = Quotas(max_connections=1)
    assert quotas.acquire_connection()
    assert not quotas.acquire_connection()
    quotas.release_connection()
    assert quotas.acquire_connection()
