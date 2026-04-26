from __future__ import annotations

import asyncio
from collections.abc import Awaitable

from .policy import SchedulerPolicy


class TaskDispatcher:
    def __init__(self, policy: SchedulerPolicy | None = None) -> None:
        self.policy = policy or SchedulerPolicy()
        self.tasks: set[asyncio.Task] = set()

    def spawn(self, coro: Awaitable):
        if len(self.tasks) >= self.policy.max_tasks:
            close = getattr(coro, 'close', None)
            if callable(close):
                close()
            raise RuntimeError('task quota exceeded')
        task = asyncio.create_task(coro)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return task


async def spawn(coro: Awaitable):
    return asyncio.create_task(coro)
