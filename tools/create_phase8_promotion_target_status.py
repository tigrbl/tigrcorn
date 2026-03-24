from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tigrcorn.compat.release_gates import evaluate_promotion_target

CONFORMANCE = ROOT / 'docs' / 'review' / 'conformance'
STATUS_JSON = CONFORMANCE / 'phase8_strict_promotion_target_status.current.json'
STATUS_MD = CONFORMANCE / 'PHASE8_STRICT_PROMOTION_TARGET_STATUS.md'


def dump_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def normalize_paths(value: Any) -> Any:
    if isinstance(value, str):
        root_text = str(ROOT.resolve())
        if value.startswith(root_text):
            try:
                return str(Path(value).resolve().relative_to(ROOT.resolve()))
            except Exception:
                return value.replace(root_text + '/', '')
        return value
    if isinstance(value, list):
        return [normalize_paths(item) for item in value]
    if isinstance(value, dict):
        return {normalize_paths(k) if isinstance(k, str) else k: normalize_paths(v) for k, v in value.items()}
    return value


def _section_lines(title: str, failures: list[str]) -> list[str]:
    lines = [f'### {title}', '']
    if failures:
        lines.extend(f'- {failure}' for failure in failures)
    else:
        lines.append('- none')
    lines.append('')
    return lines


def build_markdown(status: dict[str, Any]) -> str:
    blockers = status['blockers']
    lines = [
        '# Phase 8 strict-promotion target status',
        '',
        'This checkpoint documents the dual-boundary strict-promotion program.',
        '',
        '## Current machine-readable result',
        '',
        f"- authoritative boundary: `{status['authoritative_boundary_passed']}`",
        f"- strict target boundary: `{status['strict_target_boundary_passed']}`",
        f"- flag surface: `{status['flag_surface_passed']}`",
        f"- operator surface: `{status['operator_surface_passed']}`",
        f"- performance target: `{status['performance_passed']}`",
        f"- documentation / claim consistency: `{status['documentation_passed']}`",
        f"- composite promotion gate: `{status['final_promotion_gate_passed']}`",
        '',
        '## Current blockers',
        '',
    ]
    lines.extend(_section_lines('Strict target boundary', blockers['strict_target_boundary']))
    lines.extend(_section_lines('Flag surface', blockers['flag_surface']))
    lines.extend(_section_lines('Performance target', blockers['performance']))
    lines.extend(_section_lines('Documentation / claim consistency', blockers['documentation']))
    return '\n'.join(lines).rstrip() + '\n'


def main() -> None:
    report = evaluate_promotion_target(ROOT)
    status = {
        'phase': 8,
        'checkpoint': 'strict_promotion_targets_documented',
        'authoritative_boundary_passed': bool(report.authoritative_boundary and report.authoritative_boundary.passed),
        'strict_target_boundary_passed': bool(report.strict_target_boundary and report.strict_target_boundary.passed),
        'flag_surface_passed': bool(report.flag_surface and report.flag_surface.passed),
        'operator_surface_passed': bool(report.operator_surface and report.operator_surface.passed),
        'performance_passed': bool(report.performance and report.performance.passed),
        'documentation_passed': bool(report.documentation and report.documentation.passed),
        'final_promotion_gate_passed': report.passed,
        'blockers': {
            'strict_target_boundary': list(report.strict_target_boundary.failures if report.strict_target_boundary else []),
            'flag_surface': list(report.flag_surface.failures if report.flag_surface else []),
            'performance': list(report.performance.failures if report.performance else []),
            'documentation': list(report.documentation.failures if report.documentation else []),
        },
        'checked_files': list(report.checked_files),
    }
    dump_json(STATUS_JSON, normalize_paths(status))
    STATUS_MD.write_text(build_markdown(status), encoding='utf-8')


if __name__ == '__main__':
    main()
