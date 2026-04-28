from __future__ import annotations

import fnmatch
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from tigrcorn_config.model import ServerConfig
from tigrcorn_runtime.server.hooks import run_sync_hooks
from tigrcorn_runtime.server.signals import install_sync_signal_handlers, restore_signal_handlers

_RELOADER_ENV = 'TIGRCORN_INTERNAL_RELOADER_CHILD'


def _iter_files(roots: Iterable[str], *, include: list[str], exclude: list[str]) -> list[Path]:
    matches: list[Path] = []
    include = include or ['*.py']
    for root in roots:
        path = Path(root)
        if path.is_file():
            candidates = [path]
        elif path.exists():
            candidates = [p for p in path.rglob('*') if p.is_file()]
        else:
            continue
        for candidate in candidates:
            rel = str(candidate)
            if exclude and any(fnmatch.fnmatch(rel, pattern) for pattern in exclude):
                continue
            if include and not any(fnmatch.fnmatch(candidate.name, pattern) or fnmatch.fnmatch(rel, pattern) for pattern in include):
                continue
            matches.append(candidate)
    return sorted(set(matches))


@dataclass(slots=True)
class PollingReloader:
    argv: list[str]
    config: ServerConfig
    interval: float = 0.5
    child: subprocess.Popen[bytes] | None = None
    stopping: bool = False
    _snapshot: dict[str, float] = field(default_factory=dict)

    @classmethod
    def is_child_process(cls) -> bool:
        return os.environ.get(_RELOADER_ENV) == '1'

    def watch_roots(self) -> list[str]:
        roots = list(self.config.app.reload_dirs)
        if self.config.app.app_dir:
            roots.append(self.config.app.app_dir)
        if not roots:
            roots.append(os.getcwd())
        return roots

    def snapshot(self) -> dict[str, float]:
        values: dict[str, float] = {}
        for path in _iter_files(self.watch_roots(), include=self.config.app.reload_include, exclude=self.config.app.reload_exclude):
            try:
                values[str(path)] = path.stat().st_mtime_ns
            except FileNotFoundError:
                continue
        return values

    def spawn_child(self) -> None:
        env = os.environ.copy()
        env[_RELOADER_ENV] = '1'
        self.child = subprocess.Popen([sys.executable, '-m', 'tigrcorn', *self.argv], env=env)

    def restart_child(self) -> None:
        if self.config.hooks.on_reload:
            run_sync_hooks(self.config.hooks.on_reload, self.config)
        self.stop_child()
        self.spawn_child()

    def stop_child(self) -> None:
        if self.child is None:
            return
        if self.child.poll() is None:
            self.child.terminate()
            try:
                self.child.wait(timeout=max(1.0, self.config.http.shutdown_timeout))
            except subprocess.TimeoutExpired:
                self.child.kill()
                self.child.wait(timeout=5.0)
        self.child = None

    def run(self) -> int:
        self._snapshot = self.snapshot()
        self.spawn_child()
        previous = install_sync_signal_handlers(lambda _sig: setattr(self, 'stopping', True))
        try:
            while not self.stopping:
                time.sleep(self.interval)
                current = self.snapshot()
                if current != self._snapshot:
                    self._snapshot = current
                    self.restart_child()
                if self.child is not None and self.child.poll() not in (None, 0):
                    self.spawn_child()
            return 0
        finally:
            restore_signal_handlers(previous)
            self.stop_child()
