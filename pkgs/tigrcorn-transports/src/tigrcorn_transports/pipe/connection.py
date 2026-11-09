from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(slots=True)
class PipeConnection:
    path: str
    read_fd: int
    write_fd: int | None = None

    def read(self, n: int = 65536) -> bytes:
        return os.read(self.read_fd, n)

    def write(self, data: bytes) -> int:
        if self.write_fd is None:
            raise OSError('pipe is not writable')
        return os.write(self.write_fd, data)
