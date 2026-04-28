from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import Iterable


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
