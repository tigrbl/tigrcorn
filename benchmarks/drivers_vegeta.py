from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from benchmarks.open_loop_common import (
    latency_samples_from_percentiles,
    local_http11_target,
    parse_duration_seconds,
    parse_rate_per_second,
    require_binary,
)


def _ns_to_ms(value: int | float) -> float:
    return float(value) / 1_000_000.0


def parse_vegeta_report_json(output: str) -> dict[str, Any]:
    payload = json.loads(output)
    latencies = dict(payload.get("latencies", {}))
    p50 = _ns_to_ms(latencies.get("50th", 0))
    p95 = _ns_to_ms(latencies.get("95th", latencies.get("50th", 0)))
    p99 = _ns_to_ms(latencies.get("99th", latencies.get("95th", latencies.get("50th", 0))))
    p99_9 = _ns_to_ms(latencies.get("99.9th", latencies.get("99th", latencies.get("95th", 0))))
    requests = int(payload.get("requests", 0))
    success = float(payload.get("success", 0.0))
    error_count = int(round(requests * max(0.0, 1.0 - success)))
    duration_seconds = _ns_to_ms(payload.get("duration", 0)) / 1000.0
    return {
        "samples_ms": latency_samples_from_percentiles(p50, p95, p99, p99_9),
        "total_duration_seconds": duration_seconds,
        "total_attempts": requests,
        "total_units": requests,
        "error_count": error_count,
        "throughput_ops_per_sec": float(payload.get("throughput", payload.get("rate", 0.0))),
        "percentiles_ms": {"p50": p50, "p95": p95, "p99": p99, "p99_9": p99_9},
        "status_codes": dict(payload.get("status_codes", {})),
        "errors": list(payload.get("errors", [])),
    }


def _run_vegeta_phase(
    *,
    binary: str,
    source_root: Path,
    target_url: str,
    method: str,
    rate: str,
    duration: str,
    timeout: float,
) -> dict[str, Any]:
    target = f"{method.upper()} {target_url}"
    import subprocess

    attacked = subprocess.run(
        [binary, "attack", "-rate", rate, "-duration", duration],
        cwd=str(source_root),
        input=target.encode("utf-8"),
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if attacked.returncode != 0:
        stderr = attacked.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"vegeta attack failed with exit code {attacked.returncode}: {stderr}")
    reported = subprocess.run(
        [binary, "report", "-type=json"],
        cwd=str(source_root),
        input=attacked.stdout,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if reported.returncode != 0:
        stderr = reported.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"vegeta report failed with exit code {reported.returncode}: {stderr}")
    return parse_vegeta_report_json(reported.stdout.decode("utf-8"))


def _run_vegeta_http11(profile, *, source_root: Path) -> dict[str, Any]:
    config = dict(profile.driver_config)
    binary = str(config.get("binary", "vegeta"))
    resolved_binary = require_binary(binary)
    method = str(config.get("method", "GET"))
    path = str(config.get("path", "/plain"))
    phases = list(config.get("phases") or [])
    if not phases:
        phases = [
            {
                "name": str(config.get("phase_name", "constant")),
                "rate": str(config.get("rate", "1000/s")),
                "duration": str(config.get("duration", "30s")),
            }
        ]
    all_samples: list[float] = []
    total_duration = 0.0
    total_attempts = 0
    total_errors = 0
    phase_summaries: list[dict[str, Any]] = []
    started = time.process_time()
    with local_http11_target(source_root, path=path) as target_url:
        for phase in phases:
            rate = str(phase.get("rate", "1000/s"))
            duration = str(phase.get("duration", "30s"))
            duration_seconds = parse_duration_seconds(duration)
            parsed = _run_vegeta_phase(
                binary=resolved_binary,
                source_root=source_root,
                target_url=target_url,
                method=method,
                rate=rate,
                duration=duration,
                timeout=duration_seconds + 20.0,
            )
            all_samples.extend(float(item) for item in parsed["samples_ms"])
            total_duration += float(parsed["total_duration_seconds"])
            total_attempts += int(parsed["total_attempts"])
            total_errors += int(parsed["error_count"])
            phase_summaries.append(
                {
                    "phase_name": str(phase.get("name", "phase")),
                    "rate": rate,
                    "offered_rate": parse_rate_per_second(rate),
                    "duration_seconds": duration_seconds,
                    "target_url": target_url,
                    "percentiles_ms": parsed["percentiles_ms"],
                    "status_codes": parsed["status_codes"],
                    "errors": parsed["errors"],
                }
            )
    cpu_seconds = time.process_time() - started
    return {
        "samples_ms": all_samples,
        "total_duration_seconds": total_duration,
        "total_attempts": total_attempts,
        "total_units": total_attempts,
        "error_count": total_errors,
        "cpu_seconds": cpu_seconds,
        "rss_kib": 0.0,
        "connections": int(config.get("connections", 0)),
        "streams": 0,
        "scheduler_rejections": 0,
        "protocol_stall_counts": {},
        "correctness_checks": {
            "vegeta_completed": True,
            "responses_successful": total_errors == 0,
            "phases_completed": len(phase_summaries) == len(phases),
        },
        "correctness_note": "vegeta open-loop HTTP/1.1 benchmark pattern completed against a local Tigrcorn listener",
        "metadata": {
            "benchmark_tool": "vegeta",
            "tool_version": "vegeta report -type=json",
            "offered_rate": phase_summaries[-1]["offered_rate"] if phase_summaries else 0.0,
            "duration_seconds": total_duration,
            "connections": int(config.get("connections", 0)),
            "target_url": phase_summaries[-1]["target_url"] if phase_summaries else "",
            "pattern_name": str(config.get("pattern_name", "constant-rate")),
            "phase_name": str(config.get("phase_name", "pattern")),
            "phases": phase_summaries,
            "binary": binary,
        },
        "time_to_first_byte_ms": min(all_samples) if all_samples else 0.0,
        "handshake_latency_ms": min(all_samples) if all_samples else 0.0,
    }


def vegeta_http11_constant_rate_driver(profile, *, source_root: Path) -> dict[str, Any]:
    return _run_vegeta_http11(profile, source_root=source_root)


def vegeta_http11_step_rate_driver(profile, *, source_root: Path) -> dict[str, Any]:
    return _run_vegeta_http11(profile, source_root=source_root)


def vegeta_http11_recovery_pattern_driver(profile, *, source_root: Path) -> dict[str, Any]:
    return _run_vegeta_http11(profile, source_root=source_root)


__all__ = [
    "parse_vegeta_report_json",
    "vegeta_http11_constant_rate_driver",
    "vegeta_http11_recovery_pattern_driver",
    "vegeta_http11_step_rate_driver",
]
