from __future__ import annotations

from .imports import *
from .models import *
from .loaders import *
from .promotion_sections import *
from .docs import *
from .core import evaluate_release_gates


def load_promotion_target(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding='utf-8'))


def evaluate_promotion_target(
    source_root: str | Path,
    *,
    target_path: str | Path | None = None,
) -> PromotionTargetReport:
    source_root = Path(source_root)
    target_file = source_root / (Path(target_path) if target_path is not None else DEFAULT_PROMOTION_TARGET_PATH)
    checked_files: list[str] = [str(target_file)]
    if not target_file.exists():
        failure = f'missing promotion target file: {target_file}'
        return PromotionTargetReport(False, [failure], checked_files)

    target = load_promotion_target(target_file)

    authoritative_config = dict(target.get('authoritative_boundary', {}))
    authoritative_report = evaluate_release_gates(
        source_root,
        boundary_path=authoritative_config.get('boundary_path'),
        corpus_path=authoritative_config.get('corpus_path'),
        independent_matrix_path=authoritative_config.get('independent_matrix_path'),
        same_stack_matrix_path=authoritative_config.get('same_stack_matrix_path'),
    )
    authoritative_section = PromotionSectionReport(
        name='authoritative_boundary',
        passed=authoritative_report.passed,
        failures=list(authoritative_report.failures),
        checked_files=list(authoritative_report.checked_files),
        details={
            'boundary_path': authoritative_config.get('boundary_path', str(DEFAULT_BOUNDARY_PATH)),
            'required_rfcs': sorted(authoritative_report.rfc_status),
        },
    )

    strict_config = dict(target.get('strict_target_boundary', {}))
    strict_report = evaluate_release_gates(
        source_root,
        boundary_path=strict_config.get('boundary_path', str(DEFAULT_STRICT_TARGET_BOUNDARY_PATH)),
        corpus_path=strict_config.get('corpus_path'),
        independent_matrix_path=strict_config.get('independent_matrix_path'),
        same_stack_matrix_path=strict_config.get('same_stack_matrix_path'),
    )
    strict_section = PromotionSectionReport(
        name='strict_target_boundary',
        passed=strict_report.passed,
        failures=list(strict_report.failures),
        checked_files=list(strict_report.checked_files),
        details={
            'boundary_path': strict_config.get('boundary_path', str(DEFAULT_STRICT_TARGET_BOUNDARY_PATH)),
            'required_rfcs': sorted(strict_report.rfc_status),
        },
    )

    flag_section = _evaluate_flag_contract_target(source_root, dict(target.get('flag_surface', {})))
    operator_section = _evaluate_operator_surface_target(source_root, dict(target.get('operator_surface', {})))
    performance_section = _evaluate_performance_target(source_root, dict(target.get('performance', {})))
    documentation_section = _evaluate_documentation_claim_consistency(source_root, dict(target.get('documentation', {})))

    sections = [
        authoritative_section,
        strict_section,
        flag_section,
        operator_section,
        performance_section,
        documentation_section,
    ]

    failures: list[str] = []
    for section in sections:
        checked_files.extend(section.checked_files)
        failures.extend(f'[{section.name}] {failure}' for failure in section.failures)

    checked_files = list(dict.fromkeys(checked_files))
    return PromotionTargetReport(
        passed=all(section.passed for section in sections),
        failures=failures,
        checked_files=checked_files,
        authoritative_boundary=authoritative_section,
        strict_target_boundary=strict_section,
        flag_surface=flag_section,
        operator_surface=operator_section,
        performance=performance_section,
        documentation=documentation_section,
    )


def assert_promotion_target_ready(
    source_root: str | Path,
    *,
    target_path: str | Path | None = None,
) -> None:
    report = evaluate_promotion_target(source_root, target_path=target_path)
    if not report.passed:
        details = '\n'.join(f'- {item}' for item in report.failures)
        raise PromotionTargetError(f'promotion target failed:\n{details}')

__all__ = [name for name in globals() if not name.startswith('__')]

