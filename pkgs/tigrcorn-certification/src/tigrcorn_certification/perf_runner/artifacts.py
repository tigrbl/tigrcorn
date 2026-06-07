from __future__ import annotations

from .imports import *
from .models import *
from .stats import *
from .metrics import *

def _jsonable(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, bytes):
        try:
            return value.decode('utf-8')
        except UnicodeDecodeError:
            return value.hex()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    return repr(value)


def _write_profile_artifacts(
    profile_dir: Path,
    *,
    profile: PerfProfile,
    matrix: PerfMatrix,
    commit_hash: str,
    metrics: Mapping[str, Any],
    environment: Mapping[str, Any],
    correctness: Mapping[str, Any],
    threshold_evaluation: Mapping[str, Any],
    relative_regression: Mapping[str, Any],
    measurement: Mapping[str, Any],
    passed: bool,
    failure_reasons: list[str],
) -> None:
    histogram = _build_histogram([float(item) for item in measurement.get('samples_ms', [])])
    percentile_payload = {
        'profile_id': profile.profile_id,
        'p50_ms': metrics['p50_ms'],
        'p95_ms': metrics['p95_ms'],
        'p99_ms': metrics['p99_ms'],
        'p99_9_ms': metrics['p99_9_ms'],
        'time_to_first_byte_ms': metrics['time_to_first_byte_ms'],
        'handshake_latency_ms': metrics['handshake_latency_ms'],
        'histogram': histogram,
    }
    command_payload = {
        'argv': list(environment.get('argv', [])),
        'profile_id': profile.profile_id,
        'driver': profile.driver,
        'deployment_profile': profile.deployment_profile,
        'lane': profile.lane,
        'certification_platforms': list(profile.certification_platforms),
        'live_listener_required': profile.live_listener_required,
    }
    result_payload = {
        'profile_id': profile.profile_id,
        'family': profile.family,
        'description': profile.description,
        'driver': profile.driver,
        'deployment_profile': profile.deployment_profile,
        'lane': profile.lane,
        'certification_platforms': list(profile.certification_platforms),
        'live_listener_required': profile.live_listener_required,
        'rfc_targets': list(profile.rfc_targets),
        'commit_hash': commit_hash,
        'passed': passed,
        'metrics': dict(metrics),
        'correctness': dict(correctness),
        'threshold_evaluation': dict(threshold_evaluation),
        'relative_regression': dict(relative_regression),
        'failure_reasons': list(failure_reasons),
        'matrix_name': matrix.matrix_name,
    }
    summary_payload = {
        'profile_id': profile.profile_id,
        'lane': profile.lane,
        'deployment_profile': profile.deployment_profile,
        'passed': passed,
        'metrics': {
            'throughput_ops_per_sec': metrics['throughput_ops_per_sec'],
            'p50_ms': metrics['p50_ms'],
            'p95_ms': metrics['p95_ms'],
            'p99_ms': metrics['p99_ms'],
            'p99_9_ms': metrics['p99_9_ms'],
            'time_to_first_byte_ms': metrics['time_to_first_byte_ms'],
            'handshake_latency_ms': metrics['handshake_latency_ms'],
            'error_rate': metrics['error_rate'],
            'cpu_seconds': metrics['cpu_seconds'],
            'rss_kib': metrics['rss_kib'],
            'scheduler_rejections': metrics['scheduler_rejections'],
            'protocol_stalls': metrics['protocol_stalls'],
        },
        'certification_platforms': list(profile.certification_platforms),
        'live_listener_required': profile.live_listener_required,
        'failure_reasons': list(failure_reasons),
    }
    files = {
        'result.json': result_payload,
        'summary.json': summary_payload,
        'env.json': dict(environment),
        'percentile_histogram.json': percentile_payload,
        'command.json': command_payload,
        'correctness.json': dict(correctness),
    }
    for filename, payload in files.items():
        (profile_dir / filename).write_text(json.dumps(_jsonable(payload), indent=2, sort_keys=True) + '\n', encoding='utf-8')
    _write_samples_csv(profile_dir / 'raw_samples.csv', measurement.get('samples_ms', []))


def _write_samples_csv(path: Path, samples: list[Any]) -> None:
    lines = ['index,latency_ms']
    for index, value in enumerate(samples, start=1):
        lines.append(f'{index},{float(value):.9f}')
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def _write_run_summary(artifact_root: Path, summary: PerfRunSummary, environment: Mapping[str, Any], *, profiles: list[PerfProfile]) -> None:
    lane_counts: dict[str, int] = {}
    for profile in profiles:
        lane_counts[profile.lane] = lane_counts.get(profile.lane, 0) + 1
    payload = {
        'matrix_name': summary.matrix_name,
        'artifact_root': summary.artifact_root,
        'baseline_root': summary.baseline_root,
        'commit_hash': summary.commit_hash,
        'total': summary.total,
        'passed': summary.passed,
        'failed': summary.failed,
        'lane_counts': lane_counts,
        'certification_platform': environment.get('certification_platform'),
        'profiles': [
            {
                'profile_id': result.profile_id,
                'passed': result.passed,
                'artifact_dir': result.artifact_dir,
                'failure_reasons': result.failure_reasons,
            }
            for result in summary.profiles
        ],
        'generated_at_epoch': environment.get('generated_at_epoch'),
    }
    (artifact_root / 'summary.json').write_text(json.dumps(_jsonable(payload), indent=2, sort_keys=True) + '\n', encoding='utf-8')
    (artifact_root / 'index.json').write_text(json.dumps(_jsonable(payload), indent=2, sort_keys=True) + '\n', encoding='utf-8')
