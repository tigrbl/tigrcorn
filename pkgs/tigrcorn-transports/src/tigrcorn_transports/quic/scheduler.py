from __future__ import annotations

from dataclasses import dataclass, field
import heapq
import itertools
import time
from typing import Any


@dataclass(order=True, slots=True)
class ScheduledTimer:
    deadline: float
    sequence: int
    kind: str = field(compare=False)
    path_key: Any = field(compare=False, default=None)
    packet_space: str | None = field(compare=False, default=None)


class QuicTimerWheel:
    def __init__(self) -> None:
        self._counter = itertools.count()
        self._heap: list[ScheduledTimer] = []
        self._active: dict[tuple[str, Any, str | None], ScheduledTimer] = {}

    def now(self) -> float:
        return time.monotonic()

    def _key(self, kind: str, *, path_key: Any = None, packet_space: str | None = None) -> tuple[str, Any, str | None]:
        return kind, path_key, packet_space

    def schedule(self, kind: str, deadline: float, *, path_key: Any = None, packet_space: str | None = None) -> ScheduledTimer:
        key = self._key(kind, path_key=path_key, packet_space=packet_space)
        existing = self._active.get(key)
        if existing is not None and abs(existing.deadline - deadline) <= 1e-9:
            return existing
        timer = ScheduledTimer(deadline=deadline, sequence=next(self._counter), kind=kind, path_key=path_key, packet_space=packet_space)
        self._active[key] = timer
        heapq.heappush(self._heap, timer)
        return timer

    def cancel(self, kind: str, *, path_key: Any = None, packet_space: str | None = None) -> None:
        self._active.pop(self._key(kind, path_key=path_key, packet_space=packet_space), None)

    def next_delay(self, *, now: float | None = None) -> float | None:
        at = self.now() if now is None else now
        self._discard_stale()
        if not self._heap:
            return None
        return max(0.0, self._heap[0].deadline - at)

    def pop_due(self, *, now: float | None = None) -> list[ScheduledTimer]:
        at = self.now() if now is None else now
        due: list[ScheduledTimer] = []
        self._discard_stale()
        while self._heap and self._heap[0].deadline <= at + 1e-9:
            timer = heapq.heappop(self._heap)
            key = self._key(timer.kind, path_key=timer.path_key, packet_space=timer.packet_space)
            if self._active.get(key) is not timer:
                continue
            self._active.pop(key, None)
            due.append(timer)
        return due

    def _discard_stale(self) -> None:
        while self._heap:
            timer = self._heap[0]
            key = self._key(timer.kind, path_key=timer.path_key, packet_space=timer.packet_space)
            if self._active.get(key) is timer:
                break
            heapq.heappop(self._heap)
