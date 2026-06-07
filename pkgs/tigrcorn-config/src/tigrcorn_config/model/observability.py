from __future__ import annotations

from dataclasses import dataclass, field

from tigrcorn_core.constants import DEFAULT_LOG_LEVEL


@dataclass(slots=True)
class LoggingConfig:
    level: str = DEFAULT_LOG_LEVEL
    access_log: bool = True
    access_log_file: str | None = None
    access_log_format: str | None = None
    error_log_file: str | None = None
    log_config: str | None = None
    structured: bool = False
    use_colors: bool | None = None
    explicit_fields: list[str] = field(default_factory=list)


@dataclass(slots=True)
class MetricsConfig:
    enabled: bool = False
    bind: str | None = None
    statsd_host: str | None = None
    otel_endpoint: str | None = None
