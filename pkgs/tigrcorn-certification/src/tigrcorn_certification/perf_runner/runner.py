from __future__ import annotations

from .imports import *
from .models import *
from .stats import *
from .matrix import *
from .artifacts import *
from .environment import *
from .metrics import *

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
