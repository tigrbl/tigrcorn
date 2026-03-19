from __future__ import annotations

from dataclasses import dataclass, field
from typing import Awaitable, Callable


@dataclass(slots=True)
class ServerSupervisor:
    started: bool = False
    hooks: list[Callable[[], Awaitable[None] | None]] = field(default_factory=list)

    def add_shutdown_hook(self, hook: Callable[[], Awaitable[None] | None]) -> None:
        self.hooks.append(hook)
