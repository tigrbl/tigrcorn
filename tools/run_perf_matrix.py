#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tigrcorn.compat.perf_runner import (
    DEFAULT_BASELINE_ARTIFACT_ROOT,
    DEFAULT_CURRENT_ARTIFACT_ROOT,
    DEFAULT_PERFORMANCE_MATRIX_PATH,
    load_performance_matrix,
    run_performance_matrix,
    validate_performance_artifacts,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Run tigrcorn performance matrix profiles.')
    parser.add_argument('--matrix', default=str(DEFAULT_PERFORMANCE_MATRIX_PATH), help='Path to performance_matrix.json relative to the repository root.')
    parser.add_argument('--artifact-root', default=None, help='Artifact output root relative to the repository root.')
    parser.add_argument('--baseline-root', default=None, help='Baseline artifact root relative to the repository root.')
    parser.add_argument('--profile', action='append', dest='profiles', default=None, help='Run only the named profile id (repeatable).')
    parser.add_argument('--establish-baseline', action='store_true', help='Write baseline artifacts and skip relative regression checks.')
    parser.add_argument('--list-profiles', action='store_true', help='List profile ids and exit.')
    parser.add_argument('--list-lanes', action='store_true', help='List matrix lanes and their profile ids, then exit.')
    parser.add_argument('--validate', action='store_true', help='Validate an existing artifact root instead of running benchmarks.')
    parser.add_argument('--shuffle', action='store_true', help='Randomize profile execution order.')
    parser.add_argument('--seed', type=int, default=None, help='Random seed for reproducible shuffle (implies --shuffle).')
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    ns = parser.parse_args(argv)
    matrix = load_performance_matrix(ROOT / Path(ns.matrix))
    if ns.list_profiles:
        for profile in matrix.profiles:
            print(f'{profile.profile_id}\t{profile.lane}\t{profile.deployment_profile}')
        return 0
    if ns.list_lanes:
        lanes: dict[str, list[str]] = {}
        for profile in matrix.profiles:
            lanes.setdefault(profile.lane, []).append(profile.profile_id)
        print(json.dumps(lanes, indent=2, sort_keys=True))
        return 0
    if ns.validate:
        failures = validate_performance_artifacts(
            ROOT,
            matrix_path=ns.matrix,
            artifact_root=ns.artifact_root or (matrix.current_artifact_root if not ns.establish_baseline else matrix.baseline_artifact_root),
            baseline_root=None if ns.establish_baseline else (ns.baseline_root or matrix.baseline_artifact_root),
            require_relative_regression=not ns.establish_baseline,
        )
        if failures:
            for item in failures:
                print(f'- {item}')
            return 1
        print('performance artifacts are valid')
        return 0
    summary = run_performance_matrix(
        ROOT,
        matrix_path=ns.matrix,
        artifact_root=ns.artifact_root,
        baseline_root=None if ns.establish_baseline else ns.baseline_root,
        profile_ids=ns.profiles,
        establish_baseline=ns.establish_baseline,
        shuffle=ns.shuffle or ns.seed is not None,
        seed=ns.seed,
    )
    lane_counts: dict[str, int] = {}
    for profile in matrix.profiles:
        lane_counts[profile.lane] = lane_counts.get(profile.lane, 0) + 1
    output = {
        'matrix_name': summary.matrix_name,
        'artifact_root': summary.artifact_root,
        'baseline_root': summary.baseline_root,
        'passed': summary.passed,
        'failed': summary.failed,
        'total': summary.total,
        'lane_counts': lane_counts,
    }
    if summary.shuffle_seed is not None:
        output['shuffle_seed'] = summary.shuffle_seed
        output['execution_order'] = summary.execution_order
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0 if summary.failed == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
