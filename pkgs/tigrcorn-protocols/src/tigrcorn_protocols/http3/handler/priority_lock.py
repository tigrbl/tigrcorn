from __future__ import annotations

import asyncio
from collections import deque
from contextlib import AbstractAsyncContextManager
from types import TracebackType


class _PriorityLockContext(AbstractAsyncContextManager[None]):
    def __init__(self, lock: "PriorityLock", *, urgent: bool) -> None:
        self._lock = lock
        self._urgent = urgent
        self._acquired = False

    async def __aenter__(self) -> "_PriorityLockContext":
        await self._lock.acquire(urgent=self._urgent)
        self._acquired = True
        return self

    async def handoff(self, lock: "PriorityLock", *, urgent: bool = False) -> None:
        """Release the current lock before acquiring a narrower-scope lock."""
        if lock is self._lock:
            return
        self._lock.release()
        self._acquired = False
        self._lock = lock
        self._urgent = urgent
        await self._lock.acquire(urgent=urgent)
        self._acquired = True

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._acquired:
            self._lock.release()
            self._acquired = False


class PriorityLock(AbstractAsyncContextManager[None]):
    """FIFO async lock with a bounded-latency urgent lane.

    Current ownership is never preempted. On release, queued urgent work is
    admitted before normal work, while FIFO ordering is retained inside each
    lane.
    """

    def __init__(self) -> None:
        self._locked = False
        self._urgent_waiters: deque[asyncio.Future[None]] = deque()
        self._normal_waiters: deque[asyncio.Future[None]] = deque()

    async def acquire(self, *, urgent: bool = False) -> None:
        if not self._locked and not self._urgent_waiters and not self._normal_waiters:
            self._locked = True
            return
        loop = asyncio.get_running_loop()
        waiter: asyncio.Future[None] = loop.create_future()
        queue = self._urgent_waiters if urgent else self._normal_waiters
        queue.append(waiter)
        try:
            await waiter
        except BaseException:
            if waiter.cancelled():
                try:
                    queue.remove(waiter)
                except ValueError:
                    pass
            elif waiter.done():
                # Ownership was handed to this waiter immediately before its
                # task was cancelled. Pass it on instead of wedging the lock.
                self.release()
            else:
                waiter.cancel()
            raise

    def release(self) -> None:
        if not self._locked:
            raise RuntimeError("PriorityLock is not acquired")
        for queue in (self._urgent_waiters, self._normal_waiters):
            while queue:
                waiter = queue.popleft()
                if waiter.cancelled():
                    continue
                waiter.set_result(None)
                return
        self._locked = False

    def urgent(self) -> _PriorityLockContext:
        return _PriorityLockContext(self, urgent=True)

    def normal(self) -> _PriorityLockContext:
        return _PriorityLockContext(self, urgent=False)

    async def __aenter__(self) -> "PriorityLock":
        await self.acquire()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.release()
