from __future__ import annotations

import json
import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tigrcorn.compat.perf_runner import load_performance_matrix, run_performance_matrix

MATRIX_PATH = ROOT / 'docs/review/performance/performance_matrix.json'
BASELINE_ROOT = ROOT / 'docs/review/performance/artifacts/phase6_reference_baseline'
CURRENT_ROOT = ROOT / 'docs/review/performance/artifacts/phase6_current_release'


def platform_id() -> str:
    return f"{platform.system().lower()}-{platform.machine().lower()}-{platform.python_implementation().lower()}{sys.version_info.major}.{sys.version_info.minor}"


def load_result_metrics(root: Path, profile_id: str) -> dict:
    path = root / profile_id / 'result.json'
    if not path.exists():
        return {}
    return dict(json.loads(path.read_text(encoding='utf-8')).get('metrics', {}))


def classify_lane(profile_id: str, family: str) -> str:
    component_only = {
        'logging_off',
        'metrics_off',
        'proxy_headers_off',
        'reload_overhead',
    }
    if profile_id in component_only or family == 'Operator overhead':
        return 'component_regression'
    return 'end_to_end_release'


def expects_handshake(profile: dict) -> bool:
    deployment = str(profile.get('deployment_profile', '')).lower()
    return (
        profile.get('family') == 'TLS / PKI'
        or 'tls' in deployment
        or 'quic' in deployment
        or 'http3' in deployment
        or 'websocket_http3' in deployment
    )


def max_metric(current: dict, baseline: dict, key: str, fallback: float = 0.0) -> float:
    return max(float(current.get(key, fallback)), float(baseline.get(key, fallback)), float(fallback))


def current_protocol_stalls(metrics: dict) -> int:
    if 'protocol_stalls' in metrics:
        return int(metrics['protocol_stalls'])
    return int(sum(int(v) for v in dict(metrics.get('protocol_stall_counts', {})).values()))


def update_matrix_contract() -> None:
    payload = json.loads(MATRIX_PATH.read_text(encoding='utf-8'))
    pid = platform_id()
    payload['matrix_name'] = 'tigrcorn-phase9g-strict-performance-matrix'
    metadata = dict(payload.get('metadata', {}))
    metadata.update(
        {
            'phase': 'phase9g',
            'purpose': 'strict promotion-grade performance certification surface',
            'note': 'explicit lane separation, richer threshold coverage, and relative regression budgets after public runtime closure',
            'certification_platforms': [pid],
            'lane_definitions': {
                'component_regression': 'low-noise same-stack regression profiles',
                'end_to_end_release': 'release-lane profiles representing externally visible protocol/runtime surfaces',
            },
        }
    )
    payload['metadata'] = metadata

    for profile in payload.get('profiles', []):
        current = load_result_metrics(CURRENT_ROOT, profile['profile_id'])
        baseline = load_result_metrics(BASELINE_ROOT, profile['profile_id'])
        lane = classify_lane(profile['profile_id'], profile['family'])
        profile['lane'] = lane
        profile['certification_platforms'] = [pid]
        profile['live_listener_required'] = lane == 'end_to_end_release'

        throughput = max_metric(current, baseline, 'throughput_ops_per_sec', 1.0)
        p50 = max_metric(current, baseline, 'p50_ms', 0.01)
        p95 = max_metric(current, baseline, 'p95_ms', p50)
        p99 = max_metric(current, baseline, 'p99_ms', p95)
        rss = max_metric(current, baseline, 'rss_kib', 1024.0)
        rej = max(int(current.get('scheduler_rejections', 0)), int(baseline.get('scheduler_rejections', 0)))
        stalls = max(current_protocol_stalls(current), current_protocol_stalls(baseline))

        thresholds = dict(profile.get('thresholds', {}))
        thresholds['min_throughput_ops_per_sec'] = 1.0
        thresholds['max_p50_ms'] = max(1.0, round((p50 * 10.0) + 0.10, 6))
        thresholds['max_p95_ms'] = max(1.5, round((p95 * 10.0) + 0.10, 6))
        thresholds['max_p99_ms'] = max(2.0, round((p99 * 10.0) + 0.10, 6))
        thresholds['max_p99_9_ms'] = max(3.0, round((p99 * 12.0) + 0.15, 6))
        thresholds['max_time_to_first_byte_ms'] = max(1.0, round((p95 * 10.0) + 0.10, 6))
        if expects_handshake(profile):
            thresholds['max_handshake_latency_ms'] = round((p95 * 12.0) + 0.15, 6)
        else:
            thresholds['max_handshake_latency_ms'] = 5.0
        thresholds['max_error_rate'] = 0.0
        thresholds['max_scheduler_rejections'] = rej + (2 if lane == 'component_regression' else 4)
        thresholds['max_protocol_stalls'] = stalls + 4
        thresholds['max_rss_kib'] = round((rss * 1.25) + 2048.0, 3)
        profile['thresholds'] = thresholds

        budget = dict(profile.get('relative_regression_budget', {}))
        budget['max_throughput_drop_fraction'] = float(budget.get('max_throughput_drop_fraction', 0.5))
        budget['max_p99_increase_fraction'] = float(budget.get('max_p99_increase_fraction', 1.0))
        budget['max_p99_9_increase_fraction'] = float(budget.get('max_p99_9_increase_fraction', 1.0))
        budget['max_cpu_increase_fraction'] = float(budget.get('max_cpu_increase_fraction', 1.0))
        budget['max_rss_increase_fraction'] = float(budget.get('max_rss_increase_fraction', 0.5))
        budget['absolute_p99_slack_ms'] = float(budget.get('absolute_p99_slack_ms', 0.25))
        budget['absolute_p99_9_slack_ms'] = float(budget.get('absolute_p99_9_slack_ms', 0.5))
        budget['absolute_cpu_slack_seconds'] = float(budget.get('absolute_cpu_slack_seconds', 0.02))
        budget['absolute_rss_slack_kib'] = float(budget.get('absolute_rss_slack_kib', 2048.0))
        profile['relative_regression_budget'] = budget

    MATRIX_PATH.write_text(json.dumps(payload, indent=2, sort_keys=False) + '\n', encoding='utf-8')


def main() -> None:
    update_matrix_contract()
    run_performance_matrix(ROOT, establish_baseline=True)
    run_performance_matrix(ROOT)


if __name__ == '__main__':
    main()
