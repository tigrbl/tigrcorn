from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from tigrcorn_core.constants import (
    DEFAULT_ENV_PREFIX,
    DEFAULT_LIFESPAN,
    DEFAULT_RUNTIME,
    DEFAULT_WORKER_CLASS,
    DEFAULT_WORKER_HEALTHCHECK_TIMEOUT,
    DEFAULT_WORKERS,
)

from .types import AppInterface


@dataclass(slots=True)
class AppConfig:
    target: str | None = None
    interface: AppInterface = "auto"
    factory: bool = False
    profile: str | None = None
    app_dir: str | None = None
    config_file: str | None = None
    env_prefix: str = DEFAULT_ENV_PREFIX
    env_file: str | None = None
    lifespan: Literal["auto", "on", "off"] = DEFAULT_LIFESPAN
    reload: bool = False
    reload_dirs: list[str] = field(default_factory=list)
    reload_include: list[str] = field(default_factory=list)
    reload_exclude: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ProcessConfig:
    workers: int = DEFAULT_WORKERS
    worker_class: str = DEFAULT_WORKER_CLASS
    runtime: str = DEFAULT_RUNTIME
    pid_file: str | None = None
    worker_healthcheck_timeout: float = DEFAULT_WORKER_HEALTHCHECK_TIMEOUT
    limit_max_requests: int | None = None
    max_requests_jitter: int = 0


@dataclass(slots=True)
class HooksConfig:
    on_startup: list[Any] = field(default_factory=list)
    on_shutdown: list[Any] = field(default_factory=list)
    on_reload: list[Any] = field(default_factory=list)
