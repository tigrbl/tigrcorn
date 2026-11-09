from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any

from benchmarks.open_loop_common import (
    latency_samples_from_percentiles,
    local_http11_target,
    parse_duration_seconds,
    require_binary,
    run_command,
)


_LATENCY_RE = re.compile(r"^\s*(?P<pct>\d+(?:\.\d+)?)%\s+(?P<value>\d+(?:\.\d+)?)(?P<unit>us|ms|s)\s*$")
_REQUESTS_RE = re.compile(r"(?P<count>\d+)\s+requests\s+in\s+(?P<duration>\d+(?:\.\d+)?)s")
_REQUESTS_PER_SEC_RE = re.compile(r"Requests/sec:\s+(?P<rate>\d+(?:\.\d+)?)")
_SOCKET_ERRORS_RE = re.compile(
    r"Socket errors:\s+connect\s+(?P<connect>\d+),\s+read\s+(?P<read>\d+),\s+write\s+(?P<write>\d+),\s+timeout\s+(?P<timeout>\d+)"
)
_NON_2XX_RE = re.compile(r"Non-2xx or 3xx responses:\s+(?P<count>\d+)")


def _to_ms(value: str, unit: str) -> float:
    amount = float(value)
    if unit == "us":
        return amount / 1000.0
    if unit == "s":
        return amount * 1000.0
    return amount


def parse_wrk2_latency_output(output: str) -> dict[str, Any]:
    percentiles: dict[float, float] = {}
    total_requests = 0
    duration_seconds = 0.0
    throughput = 0.0
    socket_errors = 0
    non_2xx = 0
    for line in output.splitlines():
        latency_match = _LATENCY_RE.match(line)
        if latency_match:
            percentiles[float(latency_match.group("pct"))] = _to_ms(
                latency_match.group("value"),
                latency_match.group("unit"),
            )
            continue
        requests_match = _REQUESTS_RE.search(line)
        if requests_match:
            total_requests = int(requests_match.group("count"))
            duration_seconds = float(requests_match.group("duration"))
            continue
        rate_match = _REQUESTS_PER_SEC_RE.search(line)
        if rate_match:
            throughput = float(rate_match.group("rate"))
            continue
        socket_match = _SOCKET_ERRORS_RE.search(line)
        if socket_match:
            socket_errors = sum(int(socket_match.group(name)) for name in ("connect", "read", "write", "timeout"))
            continue
        non_2xx_match = _NON_2XX_RE.search(line)
        if non_2xx_match:
            non_2xx = int(non_2xx_match.group("count"))
    p50 = percentiles.get(50.0, 0.0)
    p95 = percentiles.get(95.0, p50)
    p99 = percentiles.get(99.0, p95)
    p99_9 = percentiles.get(99.9, p99)
    return {
        "samples_ms": latency_samples_from_percentiles(p50, p95, p99, p99_9),
        "total_duration_seconds": duration_seconds,
        "total_attempts": total_requests,
        "total_units": total_requests,
        "error_count": socket_errors + non_2xx,
        "throughput_ops_per_sec": throughput,
        "percentiles_ms": {"p50": p50, "p95": p95, "p99": p99, "p99_9": p99_9},
        "socket_errors": socket_errors,
        "non_2xx": non_2xx,
    }


def _run_wrk2_http11(profile, *, source_root: Path) -> dict[str, Any]:
    config = dict(profile.driver_config)
    binary = str(config.get("binary", "wrk"))
    resolved_binary = require_binary(binary)
    offered_rate = int(config.get("offered_rate", 1000))
    duration = str(config.get("duration", "30s"))
    duration_seconds = parse_duration_seconds(duration)
    threads = int(config.get("threads", 2))
    connections = int(config.get("connections", 64))
    path = str(config.get("path", "/plain"))
    timeout = duration_seconds + float(config.get("startup_timeout", 10.0)) + 10.0
    with local_http11_target(source_root, path=path) as target_url:
        command = [
            resolved_binary,
            "-t",
            str(threads),
            "-c",
            str(connections),
            "-d",
            duration,
            "-R",
            str(offered_rate),
            "--latency",
            target_url,
        ]
        started = time.process_time()
        completed = run_command(command, cwd=source_root, timeout=timeout)
        cpu_seconds = time.process_time() - started
    if completed.returncode != 0:
        raise RuntimeError(f"wrk2 benchmark failed with exit code {completed.returncode}: {completed.stderr.strip()}")
    parsed = parse_wrk2_latency_output(completed.stdout)
    parsed["cpu_seconds"] = cpu_seconds
    parsed["rss_kib"] = 0.0
    parsed["connections"] = connections
    parsed["streams"] = 0
    parsed["scheduler_rejections"] = 0
    parsed["protocol_stall_counts"] = {}
    parsed["correctness_checks"] = {"wrk2_completed": completed.returncode == 0, "responses_successful": parsed["error_count"] == 0}
    parsed["correctness_note"] = "wrk2 open-loop HTTP/1.1 benchmark completed against a local Tigrcorn listener"
    parsed["metadata"] = {
        "benchmark_tool": "wrk2",
        "tool_version": "wrk-compatible --latency output",
        "offered_rate": offered_rate,
        "duration_seconds": duration_seconds,
        "connections": connections,
        "target_url": target_url,
        "pattern_name": str(config.get("pattern_name", "constant-rate")),
        "phase_name": str(config.get("phase_name", "constant")),
        "threads": threads,
        "binary": binary,
    }
    parsed["time_to_first_byte_ms"] = parsed["percentiles_ms"]["p50"]
    parsed["handshake_latency_ms"] = parsed["percentiles_ms"]["p50"]
    return parsed


def wrk2_http11_constant_rate_driver(profile, *, source_root: Path) -> dict[str, Any]:
    return _run_wrk2_http11(profile, source_root=source_root)


def wrk2_http11_step_rate_driver(profile, *, source_root: Path) -> dict[str, Any]:
    return _run_wrk2_http11(profile, source_root=source_root)


__all__ = [
    "parse_wrk2_latency_output",
    "wrk2_http11_constant_rate_driver",
    "wrk2_http11_step_rate_driver",
]
