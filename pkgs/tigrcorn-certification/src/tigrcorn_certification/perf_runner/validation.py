from __future__ import annotations

from .imports import *
from .models import *
from .stats import *
from .matrix import *

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
