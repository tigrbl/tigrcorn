from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tigrcorn.config.governance_surface import governance_surface, scan_legacy_unittest_files  # noqa: E402
from tigrcorn.http.structured_fields import normalize_for_json, parse_structured_field, serialize_structured_value  # noqa: E402


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def _scan_stale_rfc8941_references(allowlist: set[str]) -> dict[str, Any]:
    checked: list[str] = []
    violations: list[str] = []
    for path in ROOT.rglob('*'):
        if not path.is_file():
            continue
        if path.suffix not in {'.md', '.json', '.py', '.toml', '.txt'}:
            continue
        relative = path.relative_to(ROOT).as_posix()
        if relative.startswith('docs/review/conformance/releases/'):
            continue
        text = path.read_text(encoding='utf-8')
        if 'RFC 8941' not in text and 'rfc8941' not in text.lower():
            continue
        checked.append(relative)
        if relative not in allowlist:
            violations.append(relative)
    return {
        'forbidden_reference': 'RFC 8941',
        'allowed_paths': sorted(allowlist),
        'checked_matches': sorted(checked),
        'violations': sorted(violations),
    }


def _render_sf_md(payload: dict[str, Any]) -> str:
    lines = [
        '# RFC 9651 Structured Fields Bundle',
        '',
        'This file is generated from the package-owned Phase 8 structured-fields metadata and implementation.',
        '',
        f"- `baseline_rfc`: `{payload['baseline_rfc']}`",
        f"- `obsolete_rfc`: `{payload['obsolete_rfc']}`",
        '',
        '## Registry',
        '',
    ]
    for name, field_type in payload['registry'].items():
        lines.append(f"- `{name}`: `{field_type}`")
    lines.extend(['', '## Sample vectors', ''])
    for row in payload['vectors']:
        lines.append(f"- `{row['field_name']}`: `{row['wire_value']}` -> `{row['canonical']}`")
    lines.extend(['', '## Stale-reference lint', ''])
    lines.append(f"- `violations`: {len(payload['stale_reference_lint']['violations'])}")
    return '\n'.join(lines) + '\n'


def _render_retention_md(title: str, rows: list[dict[str, str]]) -> str:
    lines = [f'# {title}', '', 'This file is generated from the package-owned Phase 8 governance metadata.', '']
    for row in rows:
        lines.append(f"- `{row['bundle_id']}`: `{row['path']}` ({row['role']})")
    return '\n'.join(lines) + '\n'


def generate() -> None:
    payload = governance_surface()

    detected_legacy = scan_legacy_unittest_files(ROOT)
    approved_legacy = list(payload['legacy_unittest_inventory']['approved_legacy_files'])
    unexpected_legacy = sorted(set(detected_legacy) - set(approved_legacy))
    missing_approved = sorted(set(approved_legacy) - set(detected_legacy))
    legacy_inventory = {
        'schema_version': 1,
        'forward_runner': payload['legacy_unittest_inventory']['forward_runner'],
        'inventory_mode': 'grandfathered_legacy_unittest_only',
        'policy_doc': 'docs/governance/TEST_STYLE_POLICY.md',
        'approved_legacy_files': approved_legacy,
        'detected_legacy_files': detected_legacy,
        'unexpected_legacy_files': unexpected_legacy,
        'missing_approved_files': missing_approved,
        'approved_legacy_count': len(approved_legacy),
        'detected_legacy_count': len(detected_legacy),
    }

    sf_lint = _scan_stale_rfc8941_references(set(payload['structured_fields']['stale_reference_allowlist']))
    vectors: list[dict[str, Any]] = []
    for row in payload['structured_fields']['samples']:
        parsed = parse_structured_field(row['field_name'], row['wire_value'])
        canonical = serialize_structured_value(parsed)
        reparsed = parse_structured_field(row['field_name'], canonical)
        vectors.append(
            {
                'field_name': row['field_name'],
                'expected_type': row['expected_type'],
                'wire_value': row['wire_value'],
                'canonical': canonical,
                'parsed': normalize_for_json(parsed),
                'round_trip_equal': normalize_for_json(parsed) == normalize_for_json(reparsed),
            }
        )
    sf_bundle = {
        'schema_version': 1,
        'baseline_rfc': payload['structured_fields']['baseline_rfc'],
        'obsolete_rfc': payload['structured_fields']['obsolete_rfc'],
        'registry': payload['structured_fields']['registry'],
        'vectors': vectors,
        'stale_reference_lint': sf_lint,
    }

    risk_register = {
        'schema_version': 1,
        'register_owner': 'tigrcorn-maintainers',
        'policy_doc': 'docs/governance/RISK_REGISTER_POLICY.md',
        'release_gate_policy': 'open blocking risks fail closed',
        'register': payload['risk_register'],
    }
    risk_traceability = {
        'schema_version': 1,
        'claim_graph_source': 'docs/review/conformance/claims_registry.json',
        'risk_register_source': 'docs/conformance/risk/RISK_REGISTER.json',
        'test_policy_doc': 'docs/governance/TEST_STYLE_POLICY.md',
        'default_audit_policy_doc': 'docs/governance/DEFAULT_AUDIT_POLICY.md',
        'legacy_unittest_inventory': 'LEGACY_UNITTEST_INVENTORY.json',
        'interop_retention_bundles': payload['interop_retention_bundles'],
        'performance_retention_bundles': payload['performance_retention_bundles'],
        'risks': [
            {
                'risk_id': row['risk_id'],
                'status': row['status'],
                'release_gate_blocking': row['release_gate_blocking'],
                'claim_refs': row['claim_refs'],
                'test_refs': row['test_refs'],
                'evidence_refs': row['evidence_refs'],
            }
            for row in payload['risk_register']
        ],
        'structured_fields_bundle': 'docs/conformance/sf9651.json',
    }

    _write_json(ROOT / 'LEGACY_UNITTEST_INVENTORY.json', legacy_inventory)
    _write_json(ROOT / 'docs' / 'conformance' / 'risk' / 'RISK_REGISTER.json', risk_register)
    _write_json(ROOT / 'docs' / 'conformance' / 'risk' / 'RISK_TRACEABILITY.json', risk_traceability)
    _write_json(ROOT / 'docs' / 'conformance' / 'sf9651.json', sf_bundle)
    _write_json(ROOT / 'docs' / 'conformance' / 'interop_retention.json', payload['interop_retention_bundles'])
    _write_json(ROOT / 'docs' / 'conformance' / 'perf_retention.json', payload['performance_retention_bundles'])

    (ROOT / 'docs' / 'conformance' / 'sf9651.md').write_text(_render_sf_md(sf_bundle), encoding='utf-8')
    (ROOT / 'docs' / 'conformance' / 'interop_retention.md').write_text(
        _render_retention_md('Interop Retention Bundles', payload['interop_retention_bundles']),
        encoding='utf-8',
    )
    (ROOT / 'docs' / 'conformance' / 'perf_retention.md').write_text(
        _render_retention_md('Performance Retention Bundles', payload['performance_retention_bundles']),
        encoding='utf-8',
    )


if __name__ == '__main__':
    generate()
