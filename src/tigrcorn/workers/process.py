from __future__ import annotations

import multiprocessing
from dataclasses import dataclass, field
from typing import Callable


@dataclass(slots=True)
class ProcessWorker:
    name: str = 'process'
    process: multiprocessing.Process | None = None

    def start(self, target: Callable[[], None]) -> None:
        if self.process is not None and self.process.is_alive():
            return
        self.process = multiprocessing.Process(target=target, name=self.name)
        self.process.start()

    def stop(self) -> None:
        if self.process is None:
            return
        if self.process.is_alive():
            self.process.terminate()
            self.process.join(timeout=5)
