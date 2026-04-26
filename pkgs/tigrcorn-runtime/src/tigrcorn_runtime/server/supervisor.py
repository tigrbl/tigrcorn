from __future__ import annotations

import contextlib
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tigrcorn.config.load import config_to_dict
from tigrcorn.config.model import ServerConfig
from tigrcorn.server.bootstrap import prebind_listener_sockets, run_worker_from_config_payload
from tigrcorn.server.signals import install_sync_signal_handlers, restore_signal_handlers
from tigrcorn.workers.process import ProcessWorker
from tigrcorn.workers.supervisor import WorkerSupervisor


@dataclass(slots=True)
class ServerSupervisor:
    app_target: str | None
    config: ServerConfig
    started: bool = False
    hooks: list[Any] = field(default_factory=list)
    poll_interval: float = 0.2
    bound_sockets: list[Any] = field(default_factory=list)
    workers: WorkerSupervisor = field(default_factory=lambda: WorkerSupervisor(auto_restart=True))
    _stopping: bool = False

    def add_shutdown_hook(self, hook) -> None:
        self.hooks.append(hook)

    def request_shutdown(self) -> None:
        self._stopping = True

    def _worker_payload(self) -> dict[str, Any]:
        payload = config_to_dict(self.config)
        if self.app_target is not None:
            payload.setdefault('app', {})['target'] = self.app_target
        return payload

    def _build_workers(self) -> None:
        worker_count = max(1, self.config.process.workers)
        payload = self._worker_payload()
        for index in range(worker_count):
            worker = ProcessWorker(name=f'tigrcorn-worker-{index}', healthcheck_timeout=self.config.process.worker_healthcheck_timeout)
            worker.start(run_worker_from_config_payload, payload)
            self.workers.add(worker)

    def start(self) -> None:
        if self.started:
            return
        self.bound_sockets = prebind_listener_sockets(self.config)
        if self.config.process.pid_file:
            Path(self.config.process.pid_file).write_text(str(os.getpid()))
        self._build_workers()
        self.started = True

    def replace_worker(self, index: int) -> None:
        payload = self._worker_payload()
        worker = self.workers.workers[index]
        replacement = ProcessWorker(name=f'{worker.name}-replacement', healthcheck_timeout=self.config.process.worker_healthcheck_timeout)
        replacement.start(run_worker_from_config_payload, payload)
        self.workers.replace(index, replacement)

    def poll_workers_once(self) -> list[dict[str, Any]]:
        restarted: list[dict[str, Any]] = []
        payload = self._worker_payload()
        for index, worker in enumerate(list(self.workers.workers)):
            if not isinstance(worker, ProcessWorker):
                continue
            worker.poll_ready()
            should_restart = worker.process is not None and not worker.is_alive()
            if worker.startup_timed_out() and not self._stopping:
                worker.stop(timeout=min(5.0, self.config.process.worker_healthcheck_timeout))
                should_restart = True
            if should_restart and not self._stopping:
                worker.restart_count += 1
                replacement = ProcessWorker(name=worker.name, healthcheck_timeout=self.config.process.worker_healthcheck_timeout)
                replacement.start(run_worker_from_config_payload, payload)
                self.workers.workers[index] = replacement
                restarted.append({'index': index, 'name': replacement.name, 'ready': replacement.ready})
        return restarted

    def stop(self) -> None:
        self._stopping = True
        self.workers.stop_all(timeout=self.config.http.shutdown_timeout)
        for hook in self.hooks:
            try:
                hook()
            except Exception:
                pass
        for sock in self.bound_sockets:
            try:
                sock.close()
            except Exception:
                pass
        if self.config.process.pid_file:
            with contextlib.suppress(Exception):
                Path(self.config.process.pid_file).unlink()

    def run(self) -> None:
        self.start()
        previous = install_sync_signal_handlers(lambda _sig: self.request_shutdown())
        try:
            while not self._stopping:
                self.poll_workers_once()
                time.sleep(self.poll_interval)
        finally:
            restore_signal_handlers(previous)
            self.stop()
