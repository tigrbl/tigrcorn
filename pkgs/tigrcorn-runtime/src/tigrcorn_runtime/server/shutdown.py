from __future__ import annotations

import asyncio
from contextlib import suppress


async def graceful_cancel(task: asyncio.Task | None) -> None:
    if task is None:
        return
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task
