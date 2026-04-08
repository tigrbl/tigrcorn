from __future__ import annotations

import html
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tigrcorn.compat.release_gates import evaluate_promotion_target, evaluate_release_gates  # noqa: E402


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def _version() -> str:
    pyproject = (ROOT / 'pyproject.toml').read_text(encoding='utf-8')
    for line in pyproject.splitlines():
        if line.startswith('version = '):
            return line.split('"')[1]
    raise RuntimeError('version not found in pyproject.toml')


def _release_root() -> Path:
    boundary = _load_json(ROOT / 'docs' / 'review' / 'conformance' / 'certification_boundary.json')
    return ROOT / Path(str(boundary['canonical_release_bundle']))


def _claim_report(version: str) -> dict[str, Any]:
    claims = _load_json(ROOT / 'docs' / 'review' / 'conformance' / 'claims_registry.json')
    rows = claims['current_and_candidate_claims']
    implemented = [row for row in rows if row.get('status') == 'implemented_in_tree']
    candidates = [row for row in rows if str(row.get('status', '')).startswith('candidate')]
    return {
        'schema_version': 1,
        'version': version,
        'implemented_count': len(implemented),
        'candidate_count': len(candidates),
        'implemented_ids': [row['id'] for row in implemented],
        'candidate_ids': [row['id'] for row in candidates],
    }


def _risk_status(version: str) -> dict[str, Any]:
    payload = _load_json(ROOT / 'docs' / 'conformance' / 'risk' / 'RISK_REGISTER.json')
    rows = payload['register']
    severity_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    blocking_open = 0
    for row in rows:
        severity = str(row['severity'])
        status = str(row['status'])
        severity_counts[severity] = severity_counts.get(severity, 0) + 1
        status_counts[status] = status_counts.get(status, 0) + 1
        if row.get('release_gate_blocking') and status in {'open', 'active', 'planned', 'unmitigated'}:
            blocking_open += 1
    return {
        'schema_version': 1,
        'version': version,
        'risk_count': len(rows),
        'severity_counts': severity_counts,
        'status_counts': status_counts,
        'blocking_open_count': blocking_open,
    }


def _evidence_ix(version: str, release_root: Path) -> dict[str, Any]:
    manifest = _load_json(release_root / 'manifest.json')
    bundle_index = _load_json(release_root / 'bundle_index.json')
    bundle_summary = _load_json(release_root / 'bundle_summary.json')
    return {
        'schema_version': 1,
        'version': version,
        'release_root': str(release_root.relative_to(ROOT)).replace('\\', '/'),
        'manifest': str((release_root / 'manifest.json').relative_to(ROOT)).replace('\\', '/'),
        'bundle_index': str((release_root / 'bundle_index.json').relative_to(ROOT)).replace('\\', '/'),
        'bundle_summary': str((release_root / 'bundle_summary.json').relative_to(ROOT)).replace('\\', '/'),
        'bundles': manifest['bundles'],
        'bundle_count': len(bundle_index.get('bundles', bundle_index.get('entries', []))) if isinstance(bundle_index, dict) else 0,
        'promotion_ready': bool(bundle_summary.get('promotion_ready', False)),
        'canonical_release_promoted': bool(bundle_summary.get('canonical_release_promoted', False)),
    }


def _release_auto(version: str, release_root: Path) -> dict[str, Any]:
    authoritative = evaluate_release_gates(ROOT)
    promotion = evaluate_promotion_target(ROOT)
    return {
        'schema_version': 1,
        'version': version,
        'release_root': str(release_root.relative_to(ROOT)).replace('\\', '/'),
        'release_notes': f'RELEASE_NOTES_{version}.md',
        'authoritative_boundary_passed': authoritative.passed,
        'promotion_target_passed': promotion.passed,
        'strict_target_passed': promotion.strict_target_boundary.passed,
        'operator_surface_passed': promotion.operator_surface.passed,
        'performance_passed': promotion.performance.passed,
        'documentation_passed': promotion.documentation.passed,
        'claim_report': 'docs/conformance/claim_rep.json',
        'risk_status': 'docs/conformance/risk_stat.json',
        'evidence_index': 'docs/conformance/evidence_ix.json',
    }


def _write_md(path: Path, title: str, bullets: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f'# {title}', '']
    lines.extend(f'- {item}' for item in bullets)
    lines.append('')
    path.write_text('\n'.join(lines), encoding='utf-8')


def _build_pages(version: str, release_auto: dict[str, Any]) -> None:
    pages_root = ROOT / '.artifacts' / 'pages'
    pages_root.mkdir(parents=True, exist_ok=True)
    (pages_root / '.nojekyll').write_text('', encoding='utf-8')
    html_body = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>tigrcorn {html.escape(version)} release evidence</title>
  </head>
  <body>
    <h1>tigrcorn {html.escape(version)} release evidence</h1>
    <p>Generated from the package-owned release automation metadata.</p>
    <ul>
      <li><a href="RELEASE_NOTES_{html.escape(version)}.md">Release notes</a></li>
      <li><a href="docs/conformance/evidence_ix.md">Evidence index</a></li>
      <li><a href="docs/conformance/claim_rep.md">Claim report</a></li>
      <li><a href="docs/conformance/risk_stat.md">Risk status</a></li>
      <li><a href="docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md">Current repository state</a></li>
    </ul>
    <pre>{html.escape(json.dumps(release_auto, indent=2, sort_keys=True))}</pre>
  </body>
</html>
"""
    (pages_root / 'index.html').write_text(html_body, encoding='utf-8')


def generate() -> None:
    version = _version()
    release_root = _release_root()
    claim_report = _claim_report(version)
    risk_status = _risk_status(version)
    evidence_ix = _evidence_ix(version, release_root)
    release_auto = _release_auto(version, release_root)

    _write_json(ROOT / 'docs' / 'conformance' / 'claim_rep.json', claim_report)
    _write_json(ROOT / 'docs' / 'conformance' / 'risk_stat.json', risk_status)
    _write_json(ROOT / 'docs' / 'conformance' / 'evidence_ix.json', evidence_ix)
    _write_json(ROOT / 'docs' / 'conformance' / 'release_auto.json', release_auto)

    _write_md(
        ROOT / 'docs' / 'conformance' / 'claim_rep.md',
        'Claim Report',
        [
            f"version: `{version}`",
            f"implemented claims: `{claim_report['implemented_count']}`",
            f"candidate claims: `{claim_report['candidate_count']}`",
        ],
    )
    _write_md(
        ROOT / 'docs' / 'conformance' / 'risk_stat.md',
        'Risk Status',
        [
            f"version: `{version}`",
            f"risk rows: `{risk_status['risk_count']}`",
            f"blocking open risks: `{risk_status['blocking_open_count']}`",
        ],
    )
    _write_md(
        ROOT / 'docs' / 'conformance' / 'evidence_ix.md',
        'Evidence Index',
        [
            f"version: `{version}`",
            f"release root: `{evidence_ix['release_root']}`",
            f"promotion ready: `{evidence_ix['promotion_ready']}`",
            f"canonical promoted: `{evidence_ix['canonical_release_promoted']}`",
        ],
    )
    _write_md(
        ROOT / 'docs' / 'conformance' / 'relnotes.md',
        'Generated Release Notes',
        [
            f"version: `{version}`",
            f"release notes source: `RELEASE_NOTES_{version}.md`",
            f"authoritative boundary passed: `{release_auto['authoritative_boundary_passed']}`",
            f"strict target passed: `{release_auto['strict_target_passed']}`",
            f"promotion target passed: `{release_auto['promotion_target_passed']}`",
        ],
    )
    _write_json(
        ROOT / 'docs' / 'conformance' / 'relnotes.json',
        {
            'schema_version': 1,
            'version': version,
            'release_notes': f'RELEASE_NOTES_{version}.md',
            'generated_summary': release_auto,
        },
    )
    _build_pages(version, release_auto)


if __name__ == '__main__':
    generate()
