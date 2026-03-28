from __future__ import annotations

import asyncio
import inspect
from collections.abc import Iterable
from typing import Any


async def _run_one_async(hook: Any, *args: Any, **kwargs: Any) -> None:
    result = hook(*args, **kwargs)
    if inspect.isawaitable(result):
        await result


async def run_async_hooks(hooks: Iterable[Any], *args: Any, **kwargs: Any) -> None:
    for hook in hooks:
        await _run_one_async(hook, *args, **kwargs)


def run_sync_hooks(hooks: Iterable[Any], *args: Any, **kwargs: Any) -> None:
    for hook in hooks:
        result = hook(*args, **kwargs)
        if inspect.isawaitable(result):
            asyncio.run(result)
