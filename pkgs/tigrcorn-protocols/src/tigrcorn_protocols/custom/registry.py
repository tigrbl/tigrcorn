from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Any


@dataclass(slots=True)
class CustomProtocolRegistry:
    handlers: dict[str, Callable[..., Any]] = field(default_factory=dict)

    def register(self, name: str, handler: Callable[..., Any]) -> None:
        self.handlers[name] = handler

    def get(self, name: str):
        return self.handlers[name]
