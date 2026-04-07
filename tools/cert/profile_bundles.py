from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tigrcorn.config import list_blessed_profiles, resolve_effective_profile_mapping, resolve_profile_spec  # noqa: E402


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


def _profile_filename(profile_id: str) -> Path:
    return ROOT / 'profiles' / f'{profile_id}.profile.json'


def _profile_doc_row(spec: dict[str, Any]) -> str:
    posture = spec['explicit_posture']
    return (
        f"| `{spec['profile_id']}` | {', '.join(spec['rfc_targets']) or 'operator-only'} | "
        f"`{posture['protocol_family']}` | `{posture['trusted_proxy_behavior']}` | "
        f"`{posture['static_serving']}` | `{posture['early_data']}` | "
        f"`{posture['http3_quic']}` | {spec['description']} |"
    )


def generate() -> None:
    profile_bundles: list[dict[str, Any]] = []
    readme_lines = [
        '# Blessed Profiles',
        '',
        'This folder contains the canonical Phase 1 blessed deployment profile artifacts.',
        '',
        'These JSON files are directly consumable via `tigrcorn --config <path>` because they include runtime config blocks plus profile metadata.',
        '',
        'Read next:',
        '',
        '1. `../docs/ops/profiles.md`',
        '2. `../docs/conformance/profile_bundles.md`',
        '3. `../docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md`',
        '',
    ]

    for profile_id in list_blessed_profiles():
        spec = resolve_profile_spec(profile_id)
        bundle = {
            'profile_bundle_version': 1,
            'profile_id': profile_id,
            'extends': spec['extends'],
            'description': spec['description'],
            'claim_ids': spec['claim_ids'],
            'rfc_targets': spec['rfc_targets'],
            'required_overrides': spec['required_overrides'],
            'explicit_posture': spec['explicit_posture'],
            'effective_config': resolve_effective_profile_mapping(profile_id),
        }
        profile_bundles.append(bundle)
        _write_json(_profile_filename(profile_id), bundle)
        readme_lines.extend(
            [
                f"- `{_profile_filename(profile_id).relative_to(ROOT).as_posix()}`",
                f"  - extends: `{spec['extends'] or 'none'}`",
                f"  - required overrides: `{', '.join(spec['required_overrides']) or 'none'}`",
            ]
        )

    _write_json(
        ROOT / 'docs' / 'conformance' / 'profile_bundles.json',
        {
            'bundle_version': 1,
            'profiles': profile_bundles,
        },
    )

    operator_doc = [
        '# Blessed Deployment Profiles',
        '',
        'This page is the operator-facing reference for the Phase 1 blessed deployment profiles.',
        '',
        'These profiles do not widen the current certification boundary. They freeze explicit in-bound posture inside the existing T/P/A/D/R package surface.',
        '',
        '| Profile | RFC targets | Protocol posture | Trusted proxy behavior | Static serving | Early data | QUIC/H3 | Description |',
        '|---|---|---|---|---|---|---|---|',
    ]
    for profile_id in list_blessed_profiles():
        operator_doc.append(_profile_doc_row(resolve_profile_spec(profile_id)))
    operator_doc.extend(
        [
            '',
            '## Consumption',
            '',
            '- Use `tigrcorn --config profiles/default.profile.json` for the boring safe baseline.',
            '- Use `tigrcorn --config profiles/strict-h3-edge.profile.json --ssl-certfile cert.pem --ssl-keyfile key.pem` for the explicit H3 edge posture.',
            '- Use `app.profile` in a config file or `build_config(profile=...)` in code when you want the runtime to resolve the blessed profile before applying overrides.',
            '',
            '## Required overrides',
            '',
            '- `strict-h2-origin`: `tls.certfile`, `tls.keyfile`',
            '- `strict-h3-edge`: `tls.certfile`, `tls.keyfile`',
            '- `strict-mtls-origin`: `tls.certfile`, `tls.keyfile`, `tls.ca_certs`',
            '- `static-origin`: `static.mount`',
            '',
            '## Conformance bundles',
            '',
            '- Machine-readable profile bundles: `docs/conformance/profile_bundles.json`',
            '- Runtime artifacts: `profiles/*.profile.json`',
        ]
    )
    (ROOT / 'docs' / 'ops' / 'profiles.md').write_text('\n'.join(operator_doc) + '\n', encoding='utf-8')

    conformance_doc = [
        '# Profile Conformance Bundles',
        '',
        'This document indexes the generated Phase 1 profile bundles.',
        '',
        '| Profile | Claim IDs | Required overrides | Artifact |',
        '|---|---|---|---|',
    ]
    for profile in profile_bundles:
        conformance_doc.append(
            f"| `{profile['profile_id']}` | {', '.join(profile['claim_ids'])} | "
            f"`{', '.join(profile['required_overrides']) or 'none'}` | "
            f"`profiles/{profile['profile_id']}.profile.json` |"
        )
    (ROOT / 'docs' / 'conformance' / 'profile_bundles.md').write_text('\n'.join(conformance_doc) + '\n', encoding='utf-8')
    (ROOT / 'profiles' / 'README.md').write_text('\n'.join(readme_lines) + '\n', encoding='utf-8')


if __name__ == '__main__':
    generate()
