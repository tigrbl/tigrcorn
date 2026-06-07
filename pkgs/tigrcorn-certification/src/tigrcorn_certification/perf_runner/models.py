from __future__ import annotations

from .imports import *

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
    shuffle_seed: int | None = None
    execution_order: list[str] | None = None


class PerfRunnerError(RuntimeError):
    pass
