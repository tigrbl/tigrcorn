from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass, field


@dataclass(slots=True)
class TaskSet:
    tasks: set[asyncio.Task] = field(default_factory=set)

    def add(self, task: asyncio.Task) -> None:
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def cancel_all(self) -> None:
        for task in list(self.tasks):
            task.cancel()
        for task in list(self.tasks):
            with suppress(asyncio.CancelledError):
                await task


async def cancel_tasks(tasks: list[asyncio.Task]) -> None:
    taskset = TaskSet(set(tasks))
    await taskset.cancel_all()
