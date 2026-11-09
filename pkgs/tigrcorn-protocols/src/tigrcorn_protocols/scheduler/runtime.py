from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from dataclasses import dataclass
from typing import Any

from .dispatch import TaskDispatcher
from .policy import SchedulerPolicy
from .quotas import Quotas
from .tasks import TaskSet


@dataclass(slots=True)
class ConnectionLease:
    scheduler: "ProductionScheduler"
    released: bool = False

    def release(self) -> None:
        if self.released:
            return
        self.scheduler.release_connection()
        self.released = True

    def __enter__(self) -> "ConnectionLease":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()


@dataclass(slots=True)
class WorkLease:
    scheduler: "ProductionScheduler"
    released: bool = False

    def release(self) -> None:
        if self.released:
            return
        self.scheduler.release_work()
        self.released = True

    def __enter__(self) -> "WorkLease":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()


class ProductionScheduler:
    """Package-owned runtime scheduler for connection admission and task draining.

    The scheduler keeps protocol code out of ad-hoc concurrency decisions. It owns:
    - connection quotas
    - task quotas
    - global in-flight work admission (`limit_concurrency`)
    - graceful shutdown / drain behavior
    - task tracking for server-internal relay work
    """

    def __init__(self, policy: SchedulerPolicy | None = None) -> None:
        self.policy = policy or SchedulerPolicy()
        self.dispatcher = TaskDispatcher(self.policy)
        self.quotas = Quotas(
            max_connections=self.policy.max_connections,
            max_streams_per_connection=self.policy.max_streams_per_session,
        )
        self.tasks = TaskSet()
        self._closed = False
        self._draining = False
        self._owners: dict[asyncio.Task[Any], str | None] = {}
        self._inflight = 0

    @property
    def open_connections(self) -> int:
        return self.quotas.current_connections

    @property
    def active_tasks(self) -> int:
        return len(self.dispatcher.tasks)

    @property
    def current_inflight(self) -> int:
        return self._inflight

    @property
    def closed(self) -> bool:
        return self._closed

    def _can_admit_work(self) -> bool:
        if self._closed or self._draining:
            return False
        limit = self.policy.limit_concurrency
        return limit is None or self._inflight < limit

    def acquire_connection(self) -> ConnectionLease | None:
        if self._closed or self._draining:
            return None
        if not self.quotas.acquire_connection():
            return None
        return ConnectionLease(self)

    def release_connection(self) -> None:
        self.quotas.release_connection()

    def acquire_work(self) -> WorkLease | None:
        if not self._can_admit_work():
            return None
        self._inflight += 1
        return WorkLease(self)

    def release_work(self) -> None:
        self._inflight = max(0, self._inflight - 1)

    def spawn(self, coro: Awaitable[Any], *, owner: str | None = None) -> asyncio.Task[Any]:
        if self._closed or self._draining:
            close = getattr(coro, 'close', None)
            if callable(close):
                close()
            raise RuntimeError('scheduler is closed')
        lease = self.acquire_work()
        if lease is None:
            close = getattr(coro, 'close', None)
            if callable(close):
                close()
            raise RuntimeError('concurrency limit exceeded')
        try:
            task = self.dispatcher.spawn(coro)
        except Exception:
            lease.release()
            raise
        self.tasks.add(task)
        self._owners[task] = owner
        task.add_done_callback(self._owners.pop)
        task.add_done_callback(lambda _task: lease.release())
        return task

    async def wait(self) -> None:
        if not self.dispatcher.tasks:
            return
        await asyncio.gather(*list(self.dispatcher.tasks), return_exceptions=True)

    async def drain(self, *, cancel_running: bool | None = None) -> None:
        if self._closed:
            return
        self._draining = True
        if cancel_running is None:
            cancel_running = not self.policy.drain_on_shutdown
        if cancel_running:
            await self.tasks.cancel_all()
        else:
            await self.wait()
        self._closed = True

    async def close(self) -> None:
        await self.drain()
