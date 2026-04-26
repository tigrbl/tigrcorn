from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .local import LocalWorker
from .process import ProcessWorker

WorkerType = LocalWorker | ProcessWorker


@dataclass(slots=True)
class WorkerSupervisor:
    workers: list[WorkerType] = field(default_factory=list)
    auto_restart: bool = True

    def add(self, worker: WorkerType) -> None:
        self.workers.append(worker)

    def start_all(self) -> None:
        for worker in self.workers:
            worker.start()  # type: ignore[arg-type]

    def stop_all(self, *, timeout: float = 5.0) -> None:
        for worker in self.workers:
            if isinstance(worker, ProcessWorker):
                worker.stop(timeout=timeout)
            else:
                worker.stop()

    def replace(self, index: int, worker: WorkerType | None = None, *, timeout: float = 5.0) -> WorkerType:
        current = self.workers[index]
        replacement = worker or current
        if replacement is current:
            if isinstance(current, ProcessWorker):
                current.restart(timeout=timeout)
            else:
                current.stop()
                current.start()
            return current
        if isinstance(current, ProcessWorker):
            current.stop(timeout=timeout)
        else:
            current.stop()
        self.workers[index] = replacement
        replacement.start()  # type: ignore[arg-type]
        return replacement

    def unhealthy(self) -> list[WorkerType]:
        unhealthy: list[WorkerType] = []
        for worker in self.workers:
            if isinstance(worker, ProcessWorker):
                if worker.process is not None and not worker.is_alive() and worker.process.exitcode not in (None, 0):
                    unhealthy.append(worker)
        return unhealthy

    def snapshot(self) -> list[dict[str, Any]]:
        return [worker.health() for worker in self.workers]
