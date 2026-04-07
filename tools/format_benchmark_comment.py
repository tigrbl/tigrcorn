#!/usr/bin/env python3
"""Format benchmark artifacts into a GitHub PR comment (markdown)."""
from __future__ import annotations

import json
import sys
from pathlib import Path


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def fmt_throughput(value: float) -> str:
    return f'{value:,.2f}'


def fmt_latency(value: float) -> str:
    return f'{value:.3f}'


def fmt_error_rate(value: float) -> str:
    return f'{value:.3f}'


def format_comment(summary: dict, artifact_root: Path) -> str:
    total = summary.get('total', 0)
    passed = summary.get('passed', 0)
    failed = summary.get('failed', 0)
    commit = summary.get('commit_hash', 'unknown')
    platform = summary.get('certification_platform', 'unknown')
    shuffle = summary.get('shuffle', {})
    seed = shuffle.get('seed') if shuffle else None

    lines: list[str] = []
    lines.append('## Benchmark Results\n')

    status_icon = ':white_check_mark:' if failed == 0 else ':x:'
    lines.append(f'**Status:** {status_icon} {passed}/{total} passed, {failed} failed  |  **Commit:** `{commit[:8]}`')
    meta = f'**Platform:** {platform}'
    if seed is not None:
        meta += f'  |  **Shuffle seed:** {seed}'
    lines.append(meta)
    lines.append('')

    # Collect per-profile data grouped by lane
    profiles_by_lane: dict[str, list[dict]] = {}
    failures: list[dict] = []

    for entry in summary.get('profiles', []):
        pid = entry['profile_id']
        profile_summary_path = artifact_root / pid / 'summary.json'
        if profile_summary_path.exists():
            profile_data = load_json(profile_summary_path)
        else:
            profile_data = {'lane': 'unknown', 'metrics': {}, 'passed': entry.get('passed', False)}

        profile_data['_profile_id'] = pid
        profile_data['_failure_reasons'] = entry.get('failure_reasons', [])
        profile_data['_passed'] = entry.get('passed', True)

        lane = profile_data.get('lane', 'unknown')
        profiles_by_lane.setdefault(lane, []).append(profile_data)

        if not entry.get('passed', True):
            failures.append(profile_data)

    # Failures section
    if failures:
        lines.append('### Failures\n')
        lines.append('| Profile | Reasons |')
        lines.append('|---------|---------|')
        for f in failures:
            reasons = '; '.join(f['_failure_reasons']) if f['_failure_reasons'] else 'unknown'
            lines.append(f'| {f["_profile_id"]} | {reasons} |')
        lines.append('')

    # Results by lane
    lines.append('### Results\n')

    for lane, profiles in sorted(profiles_by_lane.items()):
        count = len(profiles)
        lines.append(f'<details><summary>{lane} ({count} profiles)</summary>\n')
        lines.append('| Profile | Status | Throughput (ops/s) | p99 (ms) | p99.9 (ms) | Error Rate |')
        lines.append('|---------|--------|--------------------|----------|------------|------------|')

        for p in profiles:
            pid = p['_profile_id']
            icon = ':white_check_mark:' if p['_passed'] else ':x:'
            m = p.get('metrics', {})
            throughput = fmt_throughput(m.get('throughput_ops_per_sec', 0))
            p99 = fmt_latency(m.get('p99_ms', 0))
            p99_9 = fmt_latency(m.get('p99_9_ms', 0))
            err = fmt_error_rate(m.get('error_rate', 0))
            lines.append(f'| {pid} | {icon} | {throughput} | {p99} | {p99_9} | {err} |')

        lines.append('\n</details>\n')

    return '\n'.join(lines)


def main() -> int:
    if len(sys.argv) < 2:
        print('Usage: format_benchmark_comment.py <summary.json>', file=sys.stderr)
        return 1

    summary_path = Path(sys.argv[1])
    if not summary_path.exists():
        print(f'Error: {summary_path} not found', file=sys.stderr)
        return 1

    artifact_root = summary_path.parent
    summary = load_json(summary_path)
    print(format_comment(summary, artifact_root))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
