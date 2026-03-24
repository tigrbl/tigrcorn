from __future__ import annotations

import multiprocessing
import os
import signal
from dataclasses import dataclass, field
from time import monotonic
from typing import Any, Callable


@dataclass(slots=True)
class ProcessWorker:
    name: str = 'process'
    process: multiprocessing.Process | None = None
    target: Callable[..., None] | None = None
    args: tuple[Any, ...] = field(default_factory=tuple)
    kwargs: dict[str, Any] = field(default_factory=dict)
    start_count: int = 0
    restart_count: int = 0
    last_started_at: float | None = None

    def _ctx(self) -> multiprocessing.context.BaseContext:
        if os.name == 'posix':
            try:
                return multiprocessing.get_context('fork')
            except ValueError:
                pass
        return multiprocessing.get_context()

    def start(self, target: Callable[..., None] | None = None, *args: Any, **kwargs: Any) -> None:
        if target is not None:
            self.target = target
            self.args = args
            self.kwargs = kwargs
        if self.target is None:
            raise RuntimeError('process worker target is not configured')
        if self.process is not None and self.process.is_alive():
            return
        ctx = self._ctx()
        self.process = ctx.Process(target=self.target, args=self.args, kwargs=self.kwargs, name=self.name)
        self.process.start()
        self.start_count += 1
        self.last_started_at = monotonic()

    def stop(self, timeout: float = 5.0) -> None:
        if self.process is None:
            return
        if self.process.is_alive():
            try:
                self.process.terminate()
            except Exception:
                pass
            self.process.join(timeout=timeout)
            if self.process.is_alive():
                try:
                    os.kill(self.process.pid, signal.SIGKILL)
                except Exception:
                    pass
                self.process.join(timeout=1.0)

    def restart(self, timeout: float = 5.0) -> None:
        self.restart_count += 1
        target = self.target
        args = self.args
        kwargs = dict(self.kwargs)
        self.stop(timeout=timeout)
        self.start(target, *args, **kwargs)

    def is_alive(self) -> bool:
        return bool(self.process is not None and self.process.is_alive())

    def health(self) -> dict[str, Any]:
        return {
            'name': self.name,
            'pid': self.process.pid if self.process else None,
            'alive': self.is_alive(),
            'exitcode': self.process.exitcode if self.process else None,
            'start_count': self.start_count,
            'restart_count': self.restart_count,
            'last_started_at': self.last_started_at,
        }
