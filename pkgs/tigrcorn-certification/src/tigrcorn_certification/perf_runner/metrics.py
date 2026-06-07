from __future__ import annotations

from .imports import *
from .models import *
from .stats import *

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
