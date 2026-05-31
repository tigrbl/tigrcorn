from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass
from typing import Iterable


@dataclass(slots=True)
class CancellationResult:
    completed: int
    pending: int
    timed_out: bool


async def cancel(task: asyncio.Task | None) -> None:
    if task is None:
        return
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task


async def cancel_many(tasks: Iterable[asyncio.Task]) -> None:
    for task in tasks:
        task.cancel()
    for task in tasks:
        with suppress(asyncio.CancelledError):
            await task


async def cancel_many_bounded(tasks: Iterable[asyncio.Task], *, timeout: float) -> CancellationResult:
    task_list = list(tasks)
    for task in task_list:
        task.cancel()
    done, pending = await asyncio.wait(task_list, timeout=timeout)
    for task in done:
        with suppress(asyncio.CancelledError):
            task.result()
    return CancellationResult(completed=len(done), pending=len(pending), timed_out=bool(pending))
