from __future__ import annotations

from dataclasses import dataclass

from .base import BaseSession


@dataclass(slots=True)
class ConnectionSession(BaseSession):
    protocol: str = 'tcp'
    peer: tuple[str | None, int | None] | None = None
    server: tuple[str | None, int | None] | None = None
