from __future__ import annotations

import asyncio
import ctypes
import os
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Mapping

try:
    import resource
except ModuleNotFoundError:  # pragma: no cover - Windows fallback
    resource = None  # type: ignore[assignment]


@dataclass(slots=True)
class DriverMeasurement:
    samples_ms: list[float]
    total_duration_seconds: float
    total_attempts: int
    total_units: int
    error_count: int
    cpu_seconds: float
    rss_kib: float
    connections: int = 0
    streams: int = 0
    scheduler_rejections: int = 0
    protocol_stall_counts: dict[str, int] = field(default_factory=dict)
    correctness_checks: dict[str, bool] = field(default_factory=dict)
    correctness_note: str = 'same-stack correctness-under-load checks'
    metadata: dict[str, Any] = field(default_factory=dict)
    time_to_first_byte_ms: float | None = None
    handshake_latency_ms: float | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            'samples_ms': self.samples_ms,
            'total_duration_seconds': self.total_duration_seconds,
            'total_attempts': self.total_attempts,
            'total_units': self.total_units,
            'error_count': self.error_count,
            'cpu_seconds': self.cpu_seconds,
            'rss_kib': self.rss_kib,
            'connections': self.connections,
            'streams': self.streams,
            'scheduler_rejections': self.scheduler_rejections,
            'protocol_stall_counts': self.protocol_stall_counts,
            'correctness_checks': self.correctness_checks,
            'correctness_note': self.correctness_note,
            'metadata': self.metadata,
        }
        if self.time_to_first_byte_ms is not None:
            payload['time_to_first_byte_ms'] = self.time_to_first_byte_ms
        if self.handshake_latency_ms is not None:
            payload['handshake_latency_ms'] = self.handshake_latency_ms
        return payload


class MemoryStreamReader:
    def __init__(self, payload: bytes) -> None:
        self._payload = bytearray(payload)

    async def readexactly(self, amount: int) -> bytes:
        if amount > len(self._payload):
            from asyncio import IncompleteReadError
            partial = bytes(self._payload)
            self._payload.clear()
            raise IncompleteReadError(partial=partial, expected=amount)
        data = bytes(self._payload[:amount])
        del self._payload[:amount]
        return data

    async def readuntil(self, separator: bytes = b'\n') -> bytes:
        index = self._payload.find(separator)
        if index < 0:
            from asyncio import IncompleteReadError
            partial = bytes(self._payload)
            self._payload.clear()
            raise IncompleteReadError(partial=partial, expected=len(separator))
        end = index + len(separator)
        data = bytes(self._payload[:end])
        del self._payload[:end]
        return data


def _rss_kib() -> float:
    if resource is not None:
        usage = resource.getrusage(resource.RUSAGE_SELF)
        return float(usage.ru_maxrss)
    if os.name == 'nt':
        counters = _PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(_PROCESS_MEMORY_COUNTERS)
        process = ctypes.windll.kernel32.GetCurrentProcess()
        ok = ctypes.windll.psapi.GetProcessMemoryInfo(
            process,
            ctypes.byref(counters),
            counters.cb,
        )
        if ok:
            return float(counters.WorkingSetSize) / 1024.0
    return 0.0


class _PROCESS_MEMORY_COUNTERS(ctypes.Structure):
    _fields_ = [
        ('cb', ctypes.c_ulong),
        ('PageFaultCount', ctypes.c_ulong),
        ('PeakWorkingSetSize', ctypes.c_size_t),
        ('WorkingSetSize', ctypes.c_size_t),
        ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
        ('QuotaPagedPoolUsage', ctypes.c_size_t),
        ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
        ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
        ('PagefileUsage', ctypes.c_size_t),
        ('PeakPagefileUsage', ctypes.c_size_t),
    ]


def _accumulate_optional_latency(info: Mapping[str, Any], *, totals: dict[str, float], counts: dict[str, int], key: str) -> None:
    value = info.get(key)
    if value is None:
        return
    totals[key] = totals.get(key, 0.0) + float(value)
    counts[key] = counts.get(key, 0) + 1


def measure_sync(
    operation: Callable[[], Mapping[str, Any] | None],
    *,
    iterations: int,
    warmups: int,
    units_per_iteration: int = 1,
    correctness_note: str = 'same-stack correctness-under-load checks',
) -> dict[str, Any]:
    for _ in range(max(0, warmups)):
        operation()
    samples: list[float] = []
    connections = 0
    streams = 0
    scheduler_rejections = 0
    protocol_stalls: dict[str, int] = {}
    correctness: dict[str, bool] = {}
    metadata: dict[str, Any] = {}
    optional_latency_totals: dict[str, float] = {}
    optional_latency_counts: dict[str, int] = {}
    errors = 0
    cpu_start = time.process_time()
    rss_start = _rss_kib()
    started = time.perf_counter()
    for _ in range(iterations):
        item_started = time.perf_counter()
        try:
            info = dict(operation() or {})
        except Exception:
            errors += 1
            continue
        samples.append((time.perf_counter() - item_started) * 1000.0)
        connections += int(info.get('connections', 0))
        streams += int(info.get('streams', 0))
        scheduler_rejections += int(info.get('scheduler_rejections', 0))
        for key, value in dict(info.get('protocol_stalls', {})).items():
            protocol_stalls[key] = protocol_stalls.get(key, 0) + int(value)
        for key, value in dict(info.get('correctness', {})).items():
            correctness[key] = correctness.get(key, True) and bool(value)
        metadata.update(dict(info.get('metadata', {})))
        _accumulate_optional_latency(info, totals=optional_latency_totals, counts=optional_latency_counts, key='time_to_first_byte_ms')
        _accumulate_optional_latency(info, totals=optional_latency_totals, counts=optional_latency_counts, key='handshake_latency_ms')
    total_duration = time.perf_counter() - started
    cpu_seconds = time.process_time() - cpu_start
    rss_end = _rss_kib()
    measurement = DriverMeasurement(
        samples_ms=samples,
        total_duration_seconds=total_duration,
        total_attempts=iterations,
        total_units=iterations * max(1, units_per_iteration),
        error_count=errors,
        cpu_seconds=cpu_seconds,
        rss_kib=max(rss_start, rss_end),
        connections=connections,
        streams=streams,
        scheduler_rejections=scheduler_rejections,
        protocol_stall_counts=protocol_stalls,
        correctness_checks=correctness,
        correctness_note=correctness_note,
        metadata=metadata,
        time_to_first_byte_ms=(optional_latency_totals['time_to_first_byte_ms'] / optional_latency_counts['time_to_first_byte_ms']) if optional_latency_counts.get('time_to_first_byte_ms') else None,
        handshake_latency_ms=(optional_latency_totals['handshake_latency_ms'] / optional_latency_counts['handshake_latency_ms']) if optional_latency_counts.get('handshake_latency_ms') else None,
    )
    return measurement.to_dict()


async def _run_async_iterations(
    operation: Callable[[], Awaitable[Mapping[str, Any] | None]],
    *,
    iterations: int,
    warmups: int,
    units_per_iteration: int,
    correctness_note: str,
) -> dict[str, Any]:
    for _ in range(max(0, warmups)):
        await operation()
    samples: list[float] = []
    connections = 0
    streams = 0
    scheduler_rejections = 0
    protocol_stalls: dict[str, int] = {}
    correctness: dict[str, bool] = {}
    metadata: dict[str, Any] = {}
    optional_latency_totals: dict[str, float] = {}
    optional_latency_counts: dict[str, int] = {}
    errors = 0
    cpu_start = time.process_time()
    rss_start = _rss_kib()
    started = time.perf_counter()
    for _ in range(iterations):
        item_started = time.perf_counter()
        try:
            info = dict((await operation()) or {})
        except Exception:
            errors += 1
            continue
        samples.append((time.perf_counter() - item_started) * 1000.0)
        connections += int(info.get('connections', 0))
        streams += int(info.get('streams', 0))
        scheduler_rejections += int(info.get('scheduler_rejections', 0))
        for key, value in dict(info.get('protocol_stalls', {})).items():
            protocol_stalls[key] = protocol_stalls.get(key, 0) + int(value)
        for key, value in dict(info.get('correctness', {})).items():
            correctness[key] = correctness.get(key, True) and bool(value)
        metadata.update(dict(info.get('metadata', {})))
        _accumulate_optional_latency(info, totals=optional_latency_totals, counts=optional_latency_counts, key='time_to_first_byte_ms')
        _accumulate_optional_latency(info, totals=optional_latency_totals, counts=optional_latency_counts, key='handshake_latency_ms')
    total_duration = time.perf_counter() - started
    cpu_seconds = time.process_time() - cpu_start
    rss_end = _rss_kib()
    measurement = DriverMeasurement(
        samples_ms=samples,
        total_duration_seconds=total_duration,
        total_attempts=iterations,
        total_units=iterations * max(1, units_per_iteration),
        error_count=errors,
        cpu_seconds=cpu_seconds,
        rss_kib=max(rss_start, rss_end),
        connections=connections,
        streams=streams,
        scheduler_rejections=scheduler_rejections,
        protocol_stall_counts=protocol_stalls,
        correctness_checks=correctness,
        correctness_note=correctness_note,
        metadata=metadata,
        time_to_first_byte_ms=(optional_latency_totals['time_to_first_byte_ms'] / optional_latency_counts['time_to_first_byte_ms']) if optional_latency_counts.get('time_to_first_byte_ms') else None,
        handshake_latency_ms=(optional_latency_totals['handshake_latency_ms'] / optional_latency_counts['handshake_latency_ms']) if optional_latency_counts.get('handshake_latency_ms') else None,
    )
    return measurement.to_dict()


def measure_async(
    operation: Callable[[], Awaitable[Mapping[str, Any] | None]],
    *,
    iterations: int,
    warmups: int,
    units_per_iteration: int = 1,
    correctness_note: str = 'same-stack correctness-under-load checks',
) -> dict[str, Any]:
    return asyncio.run(
        _run_async_iterations(
            operation,
            iterations=iterations,
            warmups=warmups,
            units_per_iteration=units_per_iteration,
            correctness_note=correctness_note,
        )
    )
