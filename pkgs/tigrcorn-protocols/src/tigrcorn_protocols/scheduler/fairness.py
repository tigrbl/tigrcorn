from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Generic, TypeVar

T = TypeVar('T')


@dataclass(slots=True)
class FairnessPolicy(Generic[T]):
    round_robin: bool = True
    _queue: deque[T] = field(default_factory=deque)

    def push(self, item: T) -> None:
        self._queue.append(item)

    def pop(self) -> T | None:
        if not self._queue:
            return None
        return self._queue.popleft()
