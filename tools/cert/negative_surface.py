from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tigrcorn.config.negative_surface import FAIL_STATE_REGISTRY, NEGATIVE_BUNDLE_METADATA, NEGATIVE_CORPORA  # noqa: E402


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def _render_registry_md(payload: dict[str, Any]) -> str:
    lines = [
        '# Fail-State Registry',
        '',
        'This file is generated from the package-owned Phase 7 negative-certification metadata.',
        '',
        '| Surface | Default action | Risk | Runtime contract | Observable outcomes |',
        '|---|---|---|---|---|',
    ]
    for row in payload['registry']:
        outcomes = ', '.join(row['observable_outcomes'])
        lines.append(f"| `{row['surface']}` | `{row['default_action']}` | {row['risk']} | {row['runtime_contract']} | {outcomes} |")
    return '\n'.join(lines) + '\n'


def _render_corpora_md(payload: dict[str, Any]) -> str:
    lines = [
        '# Negative Corpora',
        '',
        'This file is generated from the package-owned Phase 7 negative-certification metadata.',
        '',
    ]
    for surface, cases in payload['corpora'].items():
        lines.extend([f'## {surface}', '', '| Case | Expected action | Expected outcome | Tests | Preserved artifacts |', '|---|---|---|---|---|'])
        for row in cases:
            tests = ', '.join(f'`{item}`' for item in row['tests'])
            artifacts = ', '.join(f'`{item}`' for item in row['preserved_artifacts']) or ''
            lines.append(f"| `{row['id']}` | `{row['expected_action']}` | {row['expected_outcome']} | {tests} | {artifacts} |")
        lines.append('')
    return '\n'.join(lines) + '\n'


def _render_bundles_md(index_payload: dict[str, Any]) -> str:
    lines = [
        '# Negative Bundles',
        '',
        'This file is generated from the package-owned Phase 7 negative-certification metadata.',
        '',
        f"- `bundle_kind`: `{index_payload['bundle_kind']}`",
        f"- `preservation_rule`: {index_payload['preservation_rule']}",
        '',
        '| Surface | Bundle path | Case count |',
        '|---|---|---|',
    ]
    for row in index_payload['bundles']:
        lines.append(f"| `{row['surface']}` | `{row['path']}` | `{row['case_count']}` |")
    return '\n'.join(lines) + '\n'


def generate() -> None:
    registry_payload = {'contract_version': 1, 'registry': FAIL_STATE_REGISTRY}
    corpora_payload = {'contract_version': 1, 'corpora': NEGATIVE_CORPORA}
    bundle_dir = ROOT / 'docs' / 'conformance' / 'negative_bundles'
    bundle_dir.mkdir(parents=True, exist_ok=True)
    bundles = []
    for surface, cases in NEGATIVE_CORPORA.items():
        bundle_payload = {
            'contract_version': 1,
            'surface': surface,
            'bundle_kind': NEGATIVE_BUNDLE_METADATA['bundle_kind'],
            'cases': cases,
        }
        bundle_path = bundle_dir / f'{surface}.json'
        _write_json(bundle_path, bundle_payload)
        bundles.append({'surface': surface, 'path': f'docs/conformance/negative_bundles/{surface}.json', 'case_count': len(cases)})

    bundle_index = {
        'contract_version': 1,
        'bundle_kind': NEGATIVE_BUNDLE_METADATA['bundle_kind'],
        'preservation_rule': NEGATIVE_BUNDLE_METADATA['preservation_rule'],
        'bundles': bundles,
    }

    claims_path = ROOT / 'docs' / 'review' / 'conformance' / 'claims_registry.json'
    claims_payload = json.loads(claims_path.read_text(encoding='utf-8'))
    _write_json(claims_path, claims_payload)

    _write_json(ROOT / 'docs' / 'conformance' / 'fail_state_registry.json', registry_payload)
    _write_json(ROOT / 'docs' / 'conformance' / 'negative_corpora.json', corpora_payload)
    _write_json(ROOT / 'docs' / 'conformance' / 'negative_bundles.json', bundle_index)
    (ROOT / 'docs' / 'conformance' / 'fail_state_registry.md').write_text(_render_registry_md(registry_payload), encoding='utf-8')
    (ROOT / 'docs' / 'conformance' / 'negative_corpora.md').write_text(_render_corpora_md(corpora_payload), encoding='utf-8')
    (ROOT / 'docs' / 'conformance' / 'negative_bundles.md').write_text(_render_bundles_md(bundle_index), encoding='utf-8')


if __name__ == '__main__':
    generate()
