from __future__ import annotations

from .imports import *
from .models import *
from .stats import *

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
