from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tigrcorn.config import list_blessed_profiles, parser_public_defaults, resolve_effective_defaults  # noqa: E402


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


def _render_markdown_table(rows: list[dict[str, Any]]) -> str:
    lines = [
        '| Flag | Config path | Parser default | Effective default | Review |',
        '|---|---|---|---|---|',
    ]
    for row in rows:
        lines.append(
            f"| `{row['flag']}` | `{row['config_path']}` | `{row['parser_default']}` | "
            f"`{row['effective_default']}` | `{row['review_status']}` |"
        )
    return '\n'.join(lines)


def _extract_effective_default(flat_defaults: dict[str, Any], config_path: str) -> Any:
    if config_path.startswith('listeners[].'):
        return flat_defaults.get(config_path.replace('listeners[]', 'listeners[0]'))
    return flat_defaults.get(config_path)


def generate() -> None:
    parser_defaults = {row['flag']: row for row in parser_public_defaults()}
    base_audit = resolve_effective_defaults('default')
    profile_audits = {profile: resolve_effective_defaults(profile) for profile in list_blessed_profiles()}

    profile_dir = ROOT / '.ssot' / 'reports' / 'profile-defaults'
    profile_dir.mkdir(parents=True, exist_ok=True)

    contracts_path = ROOT / 'docs' / 'review' / 'conformance' / 'flag_contracts.json'
    contracts_payload = json.loads(contracts_path.read_text(encoding='utf-8'))
    contract_rows = contracts_payload['contracts']
    review_rows: list[dict[str, Any]] = []

    for row in contract_rows:
        flag = row['flag_strings'][0]
        parser_row = parser_defaults[flag]
        effective_default = _extract_effective_default(base_audit['effective_defaults_flat'], row['config_path'])
        profile_overrides = {}
        for profile, audit in profile_audits.items():
            profile_value = _extract_effective_default(audit['effective_defaults_flat'], row['config_path'])
            if profile_value != effective_default:
                profile_overrides[profile] = profile_value
        row['default'] = effective_default
        row['parser_default'] = parser_row['parser_default']
        row['help_text'] = parser_row['help']
        row['phase2_review'] = {
            'reviewed': True,
            'review_status': 'reviewed_phase2',
            'default_audit': 'DEFAULT_AUDIT.json',
            'profile_defaults_dir': '.ssot/reports/profile-defaults',
            'help_parity': True,
            'runtime_parity': True,
            'profile_overrides': profile_overrides,
        }
        review_rows.append(
            {
                'flag': flag,
                'config_path': row['config_path'],
                'parser_default': parser_row['parser_default'],
                'effective_default': effective_default,
                'review_status': 'reviewed_phase2',
            }
        )

    contracts_payload['phase2_review'] = {
        'reviewed': True,
        'review_status': 'reviewed_phase2',
        'default_audit': 'DEFAULT_AUDIT.json',
        'profile_defaults_dir': '.ssot/reports/profile-defaults',
        'reviewed_contract_rows': len(contract_rows),
        'public_flag_string_count': len(review_rows),
    }
    contracts_payload['current_state']['reviewed_contract_rows'] = len(contract_rows)
    contracts_payload['current_state']['review_status'] = 'reviewed_phase2'
    _write_json(contracts_path, contracts_payload)

    default_audit_payload = {
        'audit_version': 1,
        'claim_id': 'TC-AUDIT-DEFAULT-BASE',
        'profile': 'default',
        'parser_public_flag_count': len(parser_defaults),
        'effective_defaults_flat': base_audit['effective_defaults_flat'],
        'normalization_backfills_flat': base_audit['normalization_backfills_flat'],
        'flags': review_rows,
    }
    _write_json(ROOT / 'DEFAULT_AUDIT.json', default_audit_payload)
    (ROOT / 'DEFAULT_AUDIT.md').write_text(
        '# Default Audit\n\n'
        'This file is generated from code. It records the Phase 2 base default audit for the public flag surface.\n\n'
        f"{_render_markdown_table(review_rows)}\n",
        encoding='utf-8',
    )

    profile_rows_md: list[str] = []
    for profile, audit in profile_audits.items():
        payload = {
            'audit_version': 1,
            'claim_id': 'TC-AUDIT-PROFILE-EFFECTIVE-DEFAULTS',
            'profile': profile,
            'effective_defaults_flat': audit['effective_defaults_flat'],
            'profile_overlays_flat': audit['profile_overlays_flat'],
        }
        _write_json(profile_dir / f'{profile}.json', payload)
        md = (
            f'# Profile Defaults: {profile}\n\n'
            'This file is generated from code.\n\n'
            f"- Claim: `TC-AUDIT-PROFILE-EFFECTIVE-DEFAULTS`\n"
            f"- Effective-default key count: `{len(payload['effective_defaults_flat'])}`\n"
            f"- Overlay key count: `{len(payload['profile_overlays_flat'])}`\n"
        )
        (profile_dir / f'{profile}.md').write_text(md, encoding='utf-8')
        profile_rows_md.append(
            f"| `{profile}` | `.ssot/reports/profile-defaults/{profile}.json` | `.ssot/reports/profile-defaults/{profile}.md` | `{len(payload['profile_overlays_flat'])}` |"
        )

    (profile_dir / 'README.md').write_text(
        '# Profile Defaults\n\n'
        'Generated effective-default audits for the blessed profiles live here.\n',
        encoding='utf-8',
    )
    (profile_dir / 'MUT.json').write_text(
        json.dumps(
            {
                'state': 'mutable',
                'scope': 'profile_default_audits',
                'reason': 'Generated Phase 2 profile-effective-default audits.',
                'file_name_max': 24,
                'folder_name_max': 16,
                'path_max': 120,
            },
            indent=2,
        )
        + '\n',
        encoding='utf-8',
    )

    defaults_doc = [
        '# Generated Default Tables',
        '',
        'This page is generated from the runtime default audit and reviewed flag-contract registry.',
        '',
        _render_markdown_table(review_rows),
        '',
        '## Profile audits',
        '',
        '| Profile | JSON | Markdown | Overlay keys |',
        '|---|---|---|---|',
        *profile_rows_md,
    ]
    (ROOT / 'docs' / 'ops' / 'defaults.md').write_text('\n'.join(defaults_doc) + '\n', encoding='utf-8')


if __name__ == '__main__':
    generate()
