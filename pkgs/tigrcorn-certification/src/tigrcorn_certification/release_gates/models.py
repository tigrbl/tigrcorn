from __future__ import annotations

from .imports import *

@dataclass(slots=True)
class ReleaseGateReport:
    passed: bool
    failures: list[str] = field(default_factory=list)
    checked_files: list[str] = field(default_factory=list)
    rfc_status: dict[str, dict[str, Any]] = field(default_factory=dict)
    artifact_status: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass(slots=True)
class IndependentBundleReport:
    passed: bool
    failures: list[str] = field(default_factory=list)
    checked_files: list[str] = field(default_factory=list)
    scenario_status: dict[str, dict[str, Any]] = field(default_factory=dict)


INDEPENDENT_BUNDLE_REQUIRED_ROOT_FILES = ('manifest.json', 'summary.json', 'index.json')
INDEPENDENT_BUNDLE_REQUIRED_SCENARIO_FILES = (
    'summary.json',
    'index.json',
    'result.json',
    'scenario.json',
    'command.json',
    'env.json',
    'versions.json',
    'wire_capture.json',
)


@dataclass(slots=True)
class PromotionSectionReport:
    name: str
    passed: bool
    failures: list[str] = field(default_factory=list)
    checked_files: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PromotionTargetReport:
    passed: bool
    failures: list[str] = field(default_factory=list)
    checked_files: list[str] = field(default_factory=list)
    authoritative_boundary: PromotionSectionReport | None = None
    strict_target_boundary: PromotionSectionReport | None = None
    flag_surface: PromotionSectionReport | None = None
    operator_surface: PromotionSectionReport | None = None
    performance: PromotionSectionReport | None = None
    documentation: PromotionSectionReport | None = None


class PromotionTargetError(RuntimeError):
    pass


class ReleaseGateError(RuntimeError):
    pass

__all__ = [name for name in globals() if not name.startswith('__')]

