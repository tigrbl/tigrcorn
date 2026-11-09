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
from tigrcorn.config.audit import parser_public_defaults, resolve_effective_defaults  # noqa: E402
from tigrcorn.config.policy_surface import POLICY_GROUPS, PROXY_CONTRACT  # noqa: E402


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, bytes):
        return value.decode('latin1')
    return value


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_jsonable(payload), indent=2, sort_keys=True) + '\n', encoding='utf-8')


def _extract_effective_default(flat_defaults: dict[str, Any], config_path: str) -> Any:
    if config_path.startswith('listeners[].'):
        return flat_defaults.get(config_path.replace('listeners[]', 'listeners[0]'))
    return flat_defaults.get(config_path)


def _policy_group_rows(group: dict[str, Any], parser_rows: dict[str, dict[str, Any]], contract_rows: dict[str, dict[str, Any]], defaults: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for flag in group['flags']:
        parser_row = parser_rows[flag]
        contract_row = contract_rows[flag]
        rows.append(
            {
                'flag': flag,
                'config_path': contract_row['config_path'],
                'effective_default': _extract_effective_default(defaults, contract_row['config_path']),
                'parser_default': parser_row['parser_default'],
                'help_text': parser_row['help'],
            }
        )
    return rows


def _render_proxy_contract_md(payload: dict[str, Any]) -> str:
    lines = [
        '# Proxy Contract',
        '',
        'This file is generated from the runtime proxy contract metadata and the current parser/default surface.',
        '',
        '## Trust model',
        '',
    ]
    for key, value in payload['trust'].items():
        if isinstance(value, list):
            lines.append(f"- `{key}`: `{', '.join(value)}`")
        else:
            lines.append(f"- `{key}`: {value}")
    lines.extend(
        [
            '',
            '## Precedence table',
            '',
            '| Field | Sources | Resolution |',
            '|---|---|---|',
        ]
    )
    for row in payload['precedence']:
        lines.append(f"| `{row['field']}` | `{', '.join(row['sources'])}` | {row['selection']} |")
    lines.extend(
        [
            '',
            '## Normalization contract',
            '',
        ]
    )
    for item in payload['normalization']:
        lines.append(f'- {item}')
    return '\n'.join(lines) + '\n'


def _render_policy_md(groups: list[dict[str, Any]]) -> str:
    lines = [
        '# Policy Surface',
        '',
        'This file is generated from the shared Phase 3 policy metadata, current parser help, and runtime default audit.',
        '',
    ]
    for group in groups:
        lines.extend(
            [
                f"## {group['title']}",
                '',
                f"- Claim: `{group['claim_id']}`",
                f"- Category: `{group['category']}`",
                f"- Carriers: `{', '.join(group['carriers'])}`",
                f"- Description: {group['description']}",
                '',
                '| Flag | Config path | Effective default | Help |',
                '|---|---|---|---|',
            ]
        )
        for row in group['rows']:
            lines.append(
                f"| `{row['flag']}` | `{row['config_path']}` | `{row['effective_default']}` | {row['help_text']} |"
            )
        lines.append('')
    return '\n'.join(lines) + '\n'


def generate() -> None:
    parser_rows = {row['flag']: row for row in parser_public_defaults()}
    default_audit = resolve_effective_defaults('default')
    contracts_path = ROOT / 'docs' / 'review' / 'conformance' / 'flag_contracts.json'
    contracts_payload = json.loads(contracts_path.read_text(encoding='utf-8'))
    contract_rows = {row['flag_strings'][0]: row for row in contracts_payload['contracts']}

    policy_groups: list[dict[str, Any]] = []
    for group in POLICY_GROUPS:
        rows = _policy_group_rows(group, parser_rows, contract_rows, default_audit['effective_defaults_flat'])
        group_payload = dict(group)
        group_payload['rows'] = rows
        policy_groups.append(group_payload)
        for flag in group['flags']:
            contract_rows[flag]['phase3_contract'] = {
                'claim_id': group['claim_id'],
                'surface_id': group['surface_id'],
                'category': group['category'],
                'carriers': list(group['carriers']),
                'docs': list(group['docs']),
                'help_parity': True,
                'runtime_parity': True,
            }

    contracts_payload['phase3_review'] = {
        'reviewed': True,
        'group_count': len(policy_groups),
        'contract_doc': 'docs/conformance/proxy_contract.md',
        'policy_doc': 'docs/ops/policies.md',
        'policy_json': 'docs/conformance/policy_surface.json',
    }
    _write_json(contracts_path, contracts_payload)

    proxy_payload = {
        'contract_version': 1,
        'claim_ids': [
            'TC-CONTRACT-PROXY-TRUST',
            'TC-CONTRACT-PROXY-PRECEDENCE',
            'TC-CONTRACT-PROXY-NORMALIZATION',
        ],
        **PROXY_CONTRACT,
    }
    policy_payload = {
        'surface_version': 1,
        'generated_from': ['src/tigrcorn/config/policy_surface.py', 'src/tigrcorn/cli.py', 'DEFAULT_AUDIT.json'],
        'groups': policy_groups,
    }

    _write_json(ROOT / 'docs' / 'conformance' / 'proxy_contract.json', proxy_payload)
    _write_json(ROOT / 'docs' / 'conformance' / 'policy_surface.json', policy_payload)
    (ROOT / 'docs' / 'conformance' / 'proxy_contract.md').write_text(_render_proxy_contract_md(proxy_payload), encoding='utf-8')
    (ROOT / 'docs' / 'ops' / 'policies.md').write_text(_render_policy_md(policy_groups), encoding='utf-8')
    (ROOT / 'docs' / 'review' / 'conformance' / 'cli_help.current.txt').write_text(build_parser().format_help(), encoding='utf-8')


if __name__ == '__main__':
    generate()
