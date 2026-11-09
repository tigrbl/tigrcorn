from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Quotas:
    max_connections: int = 10_000
    max_streams_per_connection: int = 128
    current_connections: int = 0

    def acquire_connection(self) -> bool:
        if self.current_connections >= self.max_connections:
            return False
        self.current_connections += 1
        return True

    def release_connection(self) -> None:
        self.current_connections = max(0, self.current_connections - 1)
