from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tigrcorn.cli import build_parser  # noqa: E402
from tigrcorn.config.origin_surface import (  # noqa: E402
    ORIGIN_CONTRACT,
    ORIGIN_NEGATIVE_CORPUS,
    PATH_RESOLUTION_CASES,
    STATIC_OPERATOR_SURFACE,
)


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    return value


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_jsonable(payload), indent=2, sort_keys=True) + '\n', encoding='utf-8')


def _parser_rows() -> dict[str, str | None]:
    parser = build_parser()
    rows: dict[str, str | None] = {}
    for action in parser._actions:
        if action.help is None:
            continue
        for flag in action.option_strings:
            if flag.startswith('--'):
                rows[flag] = action.help
    return rows


def _render_origin_md(payload: dict[str, Any]) -> str:
    lines = [
        '# Origin Contract',
        '',
        'This file is generated from the package-owned Phase 5 origin metadata.',
        '',
        '## Public surface',
        '',
        f"- Flag group: `{payload['flag_group']}`",
        f"- Public API: `{', '.join(payload['public_api'])}`",
        '',
        '## Path resolution',
        '',
    ]
    for key, value in payload['path_resolution'].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(
        [
            '',
            '## File selection',
            '',
        ]
    )
    for key, value in payload['file_selection'].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(
        [
            '',
            '## HTTP semantics',
            '',
        ]
    )
    for key, value in payload['http_semantics'].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(
        [
            '',
            '## ASGI pathsend',
            '',
        ]
    )
    for key, value in payload['pathsend'].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(
        [
            '',
            '## Path resolution table',
            '',
            '| Request path | Decoded path | Normalized segments | Expected outcome |',
            '|---|---|---|---|',
        ]
    )
    for row in payload['path_resolution_cases']:
        normalized = 'rejected' if row['normalized_segments'] is None else '`' + '/'.join(row['normalized_segments']) + '`'
        lines.append(f"| `{row['request_path']}` | `{row['decoded_path']}` | {normalized} | {row['expected']} |")
    return '\n'.join(lines) + '\n'


def _render_negative_md(payload: dict[str, Any]) -> str:
    lines = [
        '# Origin Negative Corpus',
        '',
        'This file is generated from the package-owned Phase 5 origin metadata.',
        '',
        '| Case | Surface | Request path | Expected status | Expected outcome |',
        '|---|---|---|---|---|',
    ]
    for row in payload['cases']:
        expected_status = '' if row['expected_status'] is None else f"`{row['expected_status']}`"
        request_path = row.get('request_path', '')
        lines.append(f"| `{row['id']}` | `{row['surface']}` | `{request_path}` | {expected_status} | `{row['expected_result']}` |")
    return '\n'.join(lines) + '\n'


def _render_operator_md(payload: dict[str, Any]) -> str:
    lines = [
        '# Static Origin Operator Guide',
        '',
        'This file is generated from the package-owned Phase 5 origin metadata and the public CLI parser.',
        '',
        '## Operator controls',
        '',
        '| Surface | Config path | Help | Runtime effect |',
        '|---|---|---|---|',
    ]
    for row in payload['operator_surface']:
        help_text = row.get('help_text') or ''
        lines.append(f"| `{row['surface']}` | `{row['config_path']}` | {help_text} | {row['runtime_effect']} |")
    lines.extend(
        [
            '',
            '## Frozen behaviors',
            '',
            '- Percent-decoding happens once before mount-relative normalization.',
            '- Parent-reference segments and backslash-separated segments are denied.',
            '- Directory requests do not redirect; they either resolve to the configured index file or return 404.',
            '- Range requests bypass dynamic content coding and stay on the identity representation.',
            '- `http.response.pathsend` snapshots file length at dispatch and does not stream bytes appended later.',
        ]
    )
    return '\n'.join(lines) + '\n'


def generate() -> None:
    parser_rows = _parser_rows()
    operator_surface = []
    for row in STATIC_OPERATOR_SURFACE:
        operator_surface.append({**row, 'help_text': parser_rows.get(row['surface'])})

    origin_payload = {
        'contract_version': 1,
        **ORIGIN_CONTRACT,
        'path_resolution_cases': PATH_RESOLUTION_CASES,
    }
    negative_payload = {'contract_version': 1, 'cases': ORIGIN_NEGATIVE_CORPUS}
    operator_payload = {'contract_version': 1, 'operator_surface': operator_surface}

    contracts_path = ROOT / 'docs' / 'review' / 'conformance' / 'flag_contracts.json'
    contracts_payload = json.loads(contracts_path.read_text(encoding='utf-8'))
    contract_rows = {row['contract_id']: row for row in contracts_payload['contracts']}
    for contract_id in ('static_path_route', 'static_path_mount', 'static_path_dir_to_file', 'static_path_index_file', 'static_path_expires'):
        row = contract_rows.get(contract_id)
        if row is None:
            continue
        row['phase5_contract'] = {
            'claim_ids': [
                'TC-CONTRACT-ORIGIN-PATH-RESOLUTION',
                'TC-CONTRACT-ORIGIN-FILE-SELECTION',
                'TC-CONTRACT-ORIGIN-PATHSEND',
            ],
            'docs': ['docs/conformance/origin_contract.md', 'docs/conformance/origin_negatives.md', 'docs/ops/origin.md'],
            'help_parity': True,
            'runtime_parity': True,
        }
    contracts_payload['phase5_review'] = {
        'reviewed': True,
        'origin_contract_doc': 'docs/conformance/origin_contract.md',
        'origin_contract_json': 'docs/conformance/origin_contract.json',
        'origin_negative_doc': 'docs/conformance/origin_negatives.md',
        'origin_negative_json': 'docs/conformance/origin_negatives.json',
        'operator_doc': 'docs/ops/origin.md',
        'claim_count': 3,
    }
    _write_json(contracts_path, contracts_payload)

    _write_json(ROOT / 'docs' / 'conformance' / 'origin_contract.json', origin_payload)
    _write_json(ROOT / 'docs' / 'conformance' / 'origin_negatives.json', negative_payload)
    (ROOT / 'docs' / 'conformance' / 'origin_contract.md').write_text(_render_origin_md(origin_payload), encoding='utf-8')
    (ROOT / 'docs' / 'conformance' / 'origin_negatives.md').write_text(_render_negative_md(negative_payload), encoding='utf-8')
    (ROOT / 'docs' / 'ops' / 'origin.md').write_text(_render_operator_md(operator_payload), encoding='utf-8')
    (ROOT / 'docs' / 'review' / 'conformance' / 'cli_help.current.txt').write_text(build_parser().format_help(), encoding='utf-8')


if __name__ == '__main__':
    generate()
