"""Canonical transport admission settings for every configuration surface."""

from dataclasses import dataclass, fields
import math


@dataclass(slots=True)
class AdmissionConfig:
    max_connections_per_source: int | None = None
    max_connections_per_instance: int | None = None
    max_sessions_per_connection: int | None = None
    max_sessions_per_source: int | None = None
    max_sessions_per_instance: int | None = None
    max_active_streams_per_connection: int | None = None
    max_active_streams_per_session: int | None = None
    max_active_streams_per_source: int | None = None
    max_active_streams_per_instance: int | None = None
    connection_open_rate_per_source: float | None = None
    connection_open_burst_per_source: int | None = None
    connection_open_rate_per_instance: float | None = None
    connection_open_burst_per_instance: int | None = None
    session_open_rate_per_connection: float | None = None
    session_open_burst_per_connection: int | None = None
    session_open_rate_per_source: float | None = None
    session_open_burst_per_source: int | None = None
    session_open_rate_per_instance: float | None = None
    session_open_burst_per_instance: int | None = None
    stream_open_rate_per_connection: float | None = None
    stream_open_burst_per_connection: int | None = None
    stream_open_rate_per_session: float | None = None
    stream_open_burst_per_session: int | None = None
    stream_open_rate_per_source: float | None = None
    stream_open_burst_per_source: int | None = None
    stream_open_rate_per_instance: float | None = None
    stream_open_burst_per_instance: int | None = None
    max_tracking_entries: int = 65536
    coordinator_path: str | None = None
    owner_generation: str | None = None

    def __post_init__(self):
        self.validate()

    def validate(self):
        for field in fields(self):
            key = field.name
            value = getattr(self, key)
            if key in {"coordinator_path", "owner_generation"} or value is None:
                continue
            rate = "_rate_" in key
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value <= 0
                or (not rate and not isinstance(value, int))
            ):
                raise ValueError(
                    f"admission.{key} must be a finite positive "
                    + ("number" if rate else "integer")
                )
            if rate:
                burst = getattr(self, key.replace("_rate_", "_burst_"))
                if burst is None:
                    raise ValueError(f"admission.{key} requires its burst")
            if (
                "_burst_" in key
                and getattr(self, key.replace("_burst_", "_rate_")) is None
            ):
                raise ValueError(f"admission.{key} requires its rate")


ADMISSION_FIELDS = tuple(
    f.name
    for f in fields(AdmissionConfig)
    if f.name not in {"coordinator_path", "owner_generation"}
)


def admission_type(name):
    return float if "_rate_" in name else int
