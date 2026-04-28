from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

DEFAULT_PERFORMANCE_MATRIX_PATH = Path('docs/review/performance/performance_matrix.json')
DEFAULT_BASELINE_ARTIFACT_ROOT = Path('docs/review/performance/artifacts/phase6_reference_baseline')
DEFAULT_CURRENT_ARTIFACT_ROOT = Path('docs/review/performance/artifacts/phase6_current_release')


@dataclass(slots=True)
class PerfProfile:
    profile_id: str
    family: str
    description: str
    driver: str
    deployment_profile: str
    lane: str = 'component_regression'
    certification_platforms: list[str] = field(default_factory=list)
    live_listener_required: bool = False
    rfc_targets: list[str] = field(default_factory=list)
    correctness_required: bool = False
    hot_path: bool = False
    iterations: int = 10
    warmups: int = 1
    units_per_iteration: int = 1
    thresholds: dict[str, Any] = field(default_factory=dict)
    relative_regression_budget: dict[str, Any] = field(default_factory=dict)
    driver_config: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PerfMatrix:
    matrix_name: str
    baseline_artifact_root: str
    current_artifact_root: str
    profiles: list[PerfProfile]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PerfProfileResult:
    profile_id: str
    passed: bool
    artifact_dir: str
    failure_reasons: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    correctness: dict[str, Any] = field(default_factory=dict)
    threshold_evaluation: dict[str, Any] = field(default_factory=dict)
    relative_regression: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PerfRunSummary:
    matrix_name: str
    artifact_root: str
    baseline_root: str | None
    commit_hash: str
    total: int
    passed: int
    failed: int
    profiles: list[PerfProfileResult]


class PerfRunnerError(RuntimeError):
    pass


def load_performance_matrix(path: str | Path) -> PerfMatrix:
    payload = json.loads(Path(path).read_text(encoding='utf-8'))
    matrix_platforms = [str(item) for item in payload.get('metadata', {}).get('certification_platforms', [])]
    profiles = [
        PerfProfile(
            profile_id=item['profile_id'],
            family=item['family'],
            description=item['description'],
            driver=item['driver'],
            deployment_profile=item['deployment_profile'],
            lane=str(item.get('lane', 'component_regression')),
            certification_platforms=[str(entry) for entry in item.get('certification_platforms', matrix_platforms)],
            live_listener_required=bool(item.get('live_listener_required', False)),
            rfc_targets=list(item.get('rfc_targets', [])),
            correctness_required=bool(item.get('correctness_required', False)),
            hot_path=bool(item.get('hot_path', False)),
            iterations=int(item.get('iterations', 10)),
            warmups=int(item.get('warmups', 1)),
            units_per_iteration=int(item.get('units_per_iteration', 1)),
            thresholds=dict(item.get('thresholds', {})),
            relative_regression_budget=dict(item.get('relative_regression_budget', {})),
            driver_config=dict(item.get('driver_config', {})),
        )
        for item in payload.get('profiles', [])
    ]
    return PerfMatrix(
        matrix_name=str(payload.get('matrix_name', 'tigrcorn-performance-matrix')),
        baseline_artifact_root=str(payload.get('baseline_artifact_root', DEFAULT_BASELINE_ARTIFACT_ROOT.as_posix())),
        current_artifact_root=str(payload.get('current_artifact_root', DEFAULT_CURRENT_ARTIFACT_ROOT.as_posix())),
        profiles=profiles,
        metadata=dict(payload.get('metadata', {})),
    )


def run_performance_matrix(
    source_root: str | Path,
    *,
    matrix_path: str | Path | None = None,
    artifact_root: str | Path | None = None,
    baseline_root: str | Path | None = None,
    profile_ids: list[str] | None = None,
    establish_baseline: bool = False,
) -> PerfRunSummary:
    source_root = Path(source_root)
    matrix_file = source_root / (Path(matrix_path) if matrix_path is not None else DEFAULT_PERFORMANCE_MATRIX_PATH)
    matrix = load_performance_matrix(matrix_file)
    selected_ids = set(profile_ids or [profile.profile_id for profile in matrix.profiles])
    selected_profiles = [profile for profile in matrix.profiles if profile.profile_id in selected_ids]
    if not selected_profiles:
        raise PerfRunnerError('no performance profiles selected')

    if artifact_root is None:
        default_root = matrix.baseline_artifact_root if establish_baseline else matrix.current_artifact_root
        artifact_root = source_root / Path(default_root)
    else:
        artifact_root = source_root / Path(artifact_root)
    artifact_root = Path(artifact_root)
    artifact_root.mkdir(parents=True, exist_ok=True)

    if baseline_root is None:
        baseline_path = None if establish_baseline else source_root / Path(matrix.baseline_artifact_root)
    else:
        baseline_path = source_root / Path(baseline_root)

    commit_hash = _resolve_commit_hash(source_root)
    environment = _environment_snapshot(matrix=matrix, command=sys.argv)

    from benchmarks.registry import get_driver

    results: list[PerfProfileResult] = []
    for profile in selected_profiles:
        driver = get_driver(profile.driver)
        measurement = driver(profile, source_root=source_root)
        profile_dir = artifact_root / profile.profile_id
        profile_dir.mkdir(parents=True, exist_ok=True)
        metrics = _summarize_measurement(measurement, profile=profile)
        threshold_eval, failures = _evaluate_thresholds(profile, metrics)
        correctness = {
            'required': profile.correctness_required,
            'checks': measurement.get('correctness_checks', {}),
            'passed': all(measurement.get('correctness_checks', {}).values()) if profile.correctness_required else True,
            'note': measurement.get('correctness_note', 'same-stack correctness-under-load checks'),
            'lane': profile.lane,
            'live_listener_required': profile.live_listener_required,
        }
        if not correctness['passed']:
            failures.append('correctness-under-load checks failed')
        relative_regression = _evaluate_relative_regression(profile, metrics, baseline_path)
        if relative_regression.get('evaluated') and not relative_regression.get('passed', True):
            failures.extend(relative_regression.get('failure_reasons', []))
        _write_profile_artifacts(
            profile_dir,
            profile=profile,
            matrix=matrix,
            commit_hash=commit_hash,
            metrics=metrics,
            environment=environment,
            correctness=correctness,
            threshold_evaluation=threshold_eval,
            relative_regression=relative_regression,
            measurement=measurement,
            passed=not failures,
            failure_reasons=failures,
        )
        results.append(
            PerfProfileResult(
                profile_id=profile.profile_id,
                passed=not failures,
                artifact_dir=str(profile_dir),
                failure_reasons=failures,
                metrics=metrics,
                correctness=correctness,
                threshold_evaluation=threshold_eval,
                relative_regression=relative_regression,
            )
        )

    summary = PerfRunSummary(
        matrix_name=matrix.matrix_name,
        artifact_root=str(artifact_root),
        baseline_root=str(baseline_path) if baseline_path is not None else None,
        commit_hash=commit_hash,
        total=len(results),
        passed=sum(1 for result in results if result.passed),
        failed=sum(1 for result in results if not result.passed),
        profiles=results,
    )
    _write_run_summary(artifact_root, summary, environment, profiles=selected_profiles)
    return summary


def validate_performance_artifacts(
    source_root: str | Path,
    *,
    matrix_path: str | Path | None = None,
    artifact_root: str | Path | None = None,
    baseline_root: str | Path | None = None,
    require_relative_regression: bool = False,
) -> list[str]:
    source_root = Path(source_root)
    matrix_file = source_root / (Path(matrix_path) if matrix_path is not None else DEFAULT_PERFORMANCE_MATRIX_PATH)
    matrix = load_performance_matrix(matrix_file)
    artifact_base = source_root / (Path(artifact_root) if artifact_root is not None else Path(matrix.current_artifact_root))
    baseline_path = source_root / Path(baseline_root) if baseline_root is not None else None

    failures: list[str] = []
    if not artifact_base.exists():
        return [f'missing performance artifact root: {artifact_base}']

    for filename in ('summary.json', 'index.json'):
        if not (artifact_base / filename).exists():
            failures.append(f'missing performance summary file: {artifact_base / filename}')

    for profile in matrix.profiles:
        profile_dir = artifact_base / profile.profile_id
        if not profile_dir.exists():
            failures.append(f'missing profile artifact directory: {profile_dir}')
            continue
        required_files = ('result.json', 'summary.json', 'env.json', 'percentile_histogram.json', 'raw_samples.csv', 'command.json', 'correctness.json')
        missing_for_profile = False
        for filename in required_files:
            if not (profile_dir / filename).exists():
                failures.append(f'missing artifact file for {profile.profile_id}: {profile_dir / filename}')
                missing_for_profile = True
        if missing_for_profile:
            continue
        result = json.loads((profile_dir / 'result.json').read_text(encoding='utf-8'))
        if result.get('profile_id') != profile.profile_id:
            failures.append(f'{profile.profile_id} result.json does not match profile id')
        if result.get('lane') != profile.lane:
            failures.append(f'{profile.profile_id} result.json does not match configured lane')
        if not result.get('passed', False):
            failures.append(f'{profile.profile_id} performance artifact is failing: {result.get("failure_reasons", [])}')
        if profile.correctness_required and not result.get('correctness', {}).get('passed', False):
            failures.append(f'{profile.profile_id} is missing passing correctness-under-load evidence')
        if require_relative_regression and not result.get('relative_regression', {}).get('evaluated', False):
            failures.append(f'{profile.profile_id} did not evaluate relative regression against a baseline')
        if baseline_path is not None and not (baseline_path / profile.profile_id / 'result.json').exists():
            failures.append(f'missing baseline artifact for {profile.profile_id}: {baseline_path / profile.profile_id / "result.json"}')
    return failures


def _resolve_commit_hash(source_root: Path) -> str:
    env_value = os.environ.get('GIT_COMMIT') or os.environ.get('COMMIT_SHA')
    if env_value:
        return env_value
    try:
        completed = subprocess.run(
            ['git', '-C', str(source_root), 'rev-parse', 'HEAD'],
            capture_output=True,
            text=True,
            timeout=5.0,
            check=True,
        )
    except Exception:
        return 'unknown'
    value = completed.stdout.strip()
    return value or 'unknown'


def _environment_snapshot(*, matrix: PerfMatrix, command: list[str]) -> dict[str, Any]:
    clock_info = time.get_clock_info('perf_counter')
    platform_id = _default_platform_id()
    return {
        'matrix_name': matrix.matrix_name,
        'python_version': platform.python_version(),
        'python_implementation': platform.python_implementation(),
        'platform': platform.platform(),
        'machine': platform.machine(),
        'processor': platform.processor(),
        'cpu_count': os.cpu_count(),
        'perf_counter_resolution': clock_info.resolution,
        'perf_counter_monotonic': clock_info.monotonic,
        'argv': list(command),
        'generated_at_epoch': time.time(),
        'certification_platform': platform_id,
        'matrix_declared_platforms': list(matrix.metadata.get('certification_platforms', [])),
    }


def _summarize_measurement(measurement: Mapping[str, Any], *, profile: PerfProfile) -> dict[str, Any]:
    samples = [float(item) for item in measurement.get('samples_ms', [])]
    total_attempts = int(measurement.get('total_attempts', len(samples)))
    total_units = int(measurement.get('total_units', profile.units_per_iteration * total_attempts))
    total_duration = float(measurement.get('total_duration_seconds', 0.0))
    throughput = 0.0 if total_duration <= 0 else float(total_units) / total_duration
    error_count = int(measurement.get('error_count', 0))
    error_rate = 0.0 if total_attempts <= 0 else error_count / float(total_attempts)
    p50, p95, p99, p99_9 = _percentiles(samples)
    protocol_stall_counts = {str(key): int(value) for key, value in dict(measurement.get('protocol_stall_counts', {})).items()}
    protocol_stalls = sum(protocol_stall_counts.values())
    time_to_first_byte_ms = _derive_time_to_first_byte(measurement, p50)
    handshake_latency_ms = _derive_handshake_latency(measurement, p50, profile)
    return {
        'sample_count': len(samples),
        'total_attempts': total_attempts,
        'total_units': total_units,
        'total_duration_seconds': total_duration,
        'throughput_ops_per_sec': throughput,
        'p50_ms': p50,
        'p95_ms': p95,
        'p99_ms': p99,
        'p99_9_ms': p99_9,
        'time_to_first_byte_ms': time_to_first_byte_ms,
        'handshake_latency_ms': handshake_latency_ms,
        'error_count': error_count,
        'error_rate': error_rate,
        'cpu_seconds': float(measurement.get('cpu_seconds', 0.0)),
        'rss_kib': float(measurement.get('rss_kib', 0.0)),
        'connections': int(measurement.get('connections', 0)),
        'streams': int(measurement.get('streams', 0)),
        'scheduler_rejections': int(measurement.get('scheduler_rejections', 0)),
        'protocol_stalls': protocol_stalls,
        'protocol_stall_counts': protocol_stall_counts,
        'profile_metadata': dict(measurement.get('metadata', {})),
        'lane': profile.lane,
        'certification_platforms': list(profile.certification_platforms),
        'live_listener_required': profile.live_listener_required,
    }


def _evaluate_thresholds(profile: PerfProfile, metrics: Mapping[str, Any]) -> tuple[dict[str, Any], list[str]]:
    failures: list[str] = []
    thresholds = dict(profile.thresholds)
    evaluation = {'thresholds': thresholds, 'checks': {}, 'passed': True}

    def check(name: str, condition: bool, *, observed: Any, threshold: Any) -> None:
        evaluation['checks'][name] = {'observed': observed, 'threshold': threshold, 'passed': condition}
        if not condition:
            failures.append(f'{profile.profile_id} failed threshold {name}: observed={observed!r} threshold={threshold!r}')

    comparators = {
        'min_throughput_ops_per_sec': lambda observed, threshold: float(observed) >= float(threshold),
        'max_p50_ms': lambda observed, threshold: float(observed) <= float(threshold),
        'max_p95_ms': lambda observed, threshold: float(observed) <= float(threshold),
        'max_p99_ms': lambda observed, threshold: float(observed) <= float(threshold),
        'max_p99_9_ms': lambda observed, threshold: float(observed) <= float(threshold),
        'max_time_to_first_byte_ms': lambda observed, threshold: float(observed) <= float(threshold),
        'max_handshake_latency_ms': lambda observed, threshold: float(observed) <= float(threshold),
        'max_error_rate': lambda observed, threshold: float(observed) <= float(threshold),
        'max_scheduler_rejections': lambda observed, threshold: int(observed) <= int(threshold),
        'max_protocol_stalls': lambda observed, threshold: int(observed) <= int(threshold),
        'max_rss_kib': lambda observed, threshold: float(observed) <= float(threshold),
    }
    metric_map = {
        'min_throughput_ops_per_sec': 'throughput_ops_per_sec',
        'max_p50_ms': 'p50_ms',
        'max_p95_ms': 'p95_ms',
        'max_p99_ms': 'p99_ms',
        'max_p99_9_ms': 'p99_9_ms',
        'max_time_to_first_byte_ms': 'time_to_first_byte_ms',
        'max_handshake_latency_ms': 'handshake_latency_ms',
        'max_error_rate': 'error_rate',
        'max_scheduler_rejections': 'scheduler_rejections',
        'max_protocol_stalls': 'protocol_stalls',
        'max_rss_kib': 'rss_kib',
    }
    for threshold_key, comparator in comparators.items():
        if threshold_key not in thresholds:
            continue
        metric_key = metric_map[threshold_key]
        check(threshold_key, comparator(metrics[metric_key], thresholds[threshold_key]), observed=metrics[metric_key], threshold=thresholds[threshold_key])

    evaluation['passed'] = not failures
    return evaluation, failures


def _evaluate_relative_regression(profile: PerfProfile, metrics: Mapping[str, Any], baseline_root: Path | None) -> dict[str, Any]:
    if baseline_root is None:
        return {'evaluated': False, 'reason': 'no baseline root configured', 'passed': True}
    baseline_file = baseline_root / profile.profile_id / 'result.json'
    if not baseline_file.exists():
        return {'evaluated': False, 'reason': f'missing baseline artifact {baseline_file}', 'passed': True}
    baseline_payload = json.loads(baseline_file.read_text(encoding='utf-8'))
    budget = dict(profile.relative_regression_budget)
    failures: list[str] = []
    checks: dict[str, Any] = {}

    baseline_metrics = dict(baseline_payload.get('metrics', {}))
    baseline_throughput = float(baseline_metrics.get('throughput_ops_per_sec', 0.0))
    baseline_p99 = float(baseline_metrics.get('p99_ms', 0.0))
    baseline_p99_9 = float(baseline_metrics.get('p99_9_ms', baseline_p99))
    baseline_cpu = float(baseline_metrics.get('cpu_seconds', 0.0))
    baseline_rss = float(baseline_metrics.get('rss_kib', 0.0))

    throughput_drop = budget.get('max_throughput_drop_fraction')
    if throughput_drop is not None and baseline_throughput > 0.0:
        minimum_allowed = baseline_throughput * (1.0 - float(throughput_drop))
        observed = float(metrics['throughput_ops_per_sec'])
        passed = observed >= minimum_allowed
        checks['throughput_drop_fraction'] = {
            'baseline': baseline_throughput,
            'observed': observed,
            'minimum_allowed': minimum_allowed,
            'passed': passed,
        }
        if not passed:
            failures.append(f'{profile.profile_id} throughput regressed below allowed budget')

    p99_increase = budget.get('max_p99_increase_fraction')
    if p99_increase is not None and baseline_p99 > 0.0:
        absolute_slack = float(budget.get('absolute_p99_slack_ms', 0.25))
        maximum_allowed = max(baseline_p99 * (1.0 + float(p99_increase)), baseline_p99 + absolute_slack)
        observed = float(metrics['p99_ms'])
        passed = observed <= maximum_allowed
        checks['p99_increase_fraction'] = {
            'baseline': baseline_p99,
            'observed': observed,
            'maximum_allowed': maximum_allowed,
            'absolute_slack_ms': absolute_slack,
            'passed': passed,
        }
        if not passed:
            failures.append(f'{profile.profile_id} p99 latency regressed above allowed budget')

    p99_9_increase = budget.get('max_p99_9_increase_fraction')
    if p99_9_increase is not None and baseline_p99_9 > 0.0:
        absolute_slack = float(budget.get('absolute_p99_9_slack_ms', 0.5))
        maximum_allowed = max(baseline_p99_9 * (1.0 + float(p99_9_increase)), baseline_p99_9 + absolute_slack)
        observed = float(metrics['p99_9_ms'])
        passed = observed <= maximum_allowed
        checks['p99_9_increase_fraction'] = {
            'baseline': baseline_p99_9,
            'observed': observed,
            'maximum_allowed': maximum_allowed,
            'absolute_slack_ms': absolute_slack,
            'passed': passed,
        }
        if not passed:
            failures.append(f'{profile.profile_id} p99.9 latency regressed above allowed budget')

    cpu_increase = budget.get('max_cpu_increase_fraction')
    if cpu_increase is not None:
        absolute_slack = float(budget.get('absolute_cpu_slack_seconds', 0.01))
        maximum_allowed = baseline_cpu * (1.0 + float(cpu_increase)) + absolute_slack
        observed = float(metrics['cpu_seconds'])
        passed = observed <= maximum_allowed
        checks['cpu_increase_fraction'] = {
            'baseline': baseline_cpu,
            'observed': observed,
            'maximum_allowed': maximum_allowed,
            'absolute_slack_seconds': absolute_slack,
            'passed': passed,
        }
        if not passed:
            failures.append(f'{profile.profile_id} cpu time regressed above allowed budget')

    rss_increase = budget.get('max_rss_increase_fraction')
    if rss_increase is not None:
        absolute_slack = float(budget.get('absolute_rss_slack_kib', 1024.0))
        maximum_allowed = baseline_rss * (1.0 + float(rss_increase)) + absolute_slack
        observed = float(metrics['rss_kib'])
        passed = observed <= maximum_allowed
        checks['rss_increase_fraction'] = {
            'baseline': baseline_rss,
            'observed': observed,
            'maximum_allowed': maximum_allowed,
            'absolute_rss_slack_kib': absolute_slack,
            'passed': passed,
        }
        if not passed:
            failures.append(f'{profile.profile_id} rss regressed above allowed budget')

    return {
        'evaluated': True,
        'baseline_root': str(baseline_root),
        'baseline_profile': str(baseline_file),
        'checks': checks,
        'failure_reasons': failures,
        'passed': not failures,
    }


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


def _percentiles(samples: list[float]) -> tuple[float, float, float, float]:
    if not samples:
        return 0.0, 0.0, 0.0, 0.0
    ordered = sorted(samples)
    return (
        _percentile(ordered, 50.0),
        _percentile(ordered, 95.0),
        _percentile(ordered, 99.0),
        _percentile(ordered, 99.9),
    )


def _percentile(sorted_samples: list[float], pct: float) -> float:
    if not sorted_samples:
        return 0.0
    if len(sorted_samples) == 1:
        return float(sorted_samples[0])
    rank = (pct / 100.0) * (len(sorted_samples) - 1)
    low = int(rank)
    high = min(low + 1, len(sorted_samples) - 1)
    frac = rank - low
    return float(sorted_samples[low] + ((sorted_samples[high] - sorted_samples[low]) * frac))


def _build_histogram(samples: list[float], *, bucket_count: int = 8) -> list[dict[str, Any]]:
    if not samples:
        return []
    values = sorted(samples)
    minimum = values[0]
    maximum = values[-1]
    if minimum == maximum:
        return [{'lower_ms': minimum, 'upper_ms': maximum, 'count': len(values)}]
    span = maximum - minimum
    bucket_size = span / float(bucket_count)
    buckets = [{'lower_ms': minimum + (bucket_size * index), 'upper_ms': minimum + (bucket_size * (index + 1)), 'count': 0} for index in range(bucket_count)]
    for value in values:
        offset = int(min(bucket_count - 1, (value - minimum) / bucket_size))
        buckets[offset]['count'] += 1
    return buckets


def _derive_time_to_first_byte(measurement: Mapping[str, Any], default: float) -> float:
    explicit = measurement.get('time_to_first_byte_ms')
    if explicit is not None:
        return float(explicit)
    samples = measurement.get('time_to_first_byte_samples_ms')
    if isinstance(samples, list) and samples:
        ordered = sorted(float(item) for item in samples)
        return _percentile(ordered, 50.0)
    return float(default)


def _derive_handshake_latency(measurement: Mapping[str, Any], default: float, profile: PerfProfile) -> float:
    explicit = measurement.get('handshake_latency_ms')
    if explicit is not None:
        return float(explicit)
    samples = measurement.get('handshake_latency_samples_ms')
    if isinstance(samples, list) and samples:
        ordered = sorted(float(item) for item in samples)
        return _percentile(ordered, 50.0)
    if _profile_expects_handshake(profile):
        return float(default)
    return 0.0


def _profile_expects_handshake(profile: PerfProfile) -> bool:
    deployment = profile.deployment_profile.lower()
    return (
        profile.family == 'TLS / PKI'
        or 'tls' in deployment
        or 'quic' in deployment
        or 'http3' in deployment
        or 'websocket_http3' in deployment
    )


def _default_platform_id() -> str:
    implementation = platform.python_implementation().lower()
    return f"{platform.system().lower()}-{platform.machine().lower()}-{implementation}{sys.version_info.major}.{sys.version_info.minor}"


__all__ = [
    'DEFAULT_BASELINE_ARTIFACT_ROOT',
    'DEFAULT_CURRENT_ARTIFACT_ROOT',
    'DEFAULT_PERFORMANCE_MATRIX_PATH',
    'PerfMatrix',
    'PerfProfile',
    'PerfProfileResult',
    'PerfRunSummary',
    'PerfRunnerError',
    'load_performance_matrix',
    'run_performance_matrix',
    'validate_performance_artifacts',
]
