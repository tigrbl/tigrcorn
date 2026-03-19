from __future__ import annotations

from dataclasses import dataclass, field

from .local import LocalWorker


@dataclass(slots=True)
class WorkerSupervisor:
    workers: list[LocalWorker] = field(default_factory=list)

    def add(self, worker: LocalWorker) -> None:
        self.workers.append(worker)

    def start_all(self) -> None:
        for worker in self.workers:
            worker.start()

    def stop_all(self) -> None:
        for worker in self.workers:
            worker.stop()
