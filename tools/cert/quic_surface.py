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
from tigrcorn.config.quic_surface import EARLY_DATA_CONTRACT, QUIC_STATE_CLAIMS  # noqa: E402


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


def _render_early_data_md(payload: dict[str, Any]) -> str:
    lines = [
        '# Early-Data Contract',
        '',
        'This file is generated from the runtime Phase 4 QUIC metadata and the canonical independent HTTP/3 release matrix.',
        '',
        '## Public surface',
        '',
        f"- Flag: `{payload['flag']}`",
        f"- Config path: `{payload['config_path']}`",
        f"- Default policy: `{payload['default_policy']}`",
        f"- Value space: `{', '.join(payload['value_space'])}`",
        '',
        '## Admission policy',
        '',
    ]
    for key, value in payload['admission'].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(
        [
            '',
            '## Replay and 425 behavior',
            '',
        ]
    )
    for key, value in payload['replay_policy'].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(
        [
            '',
            '## Multi-instance and load-balancer policy',
            '',
        ]
    )
    for key, value in payload['topology'].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(
        [
            '',
            '## Retry and app/runtime visibility',
            '',
        ]
    )
    for key, value in payload['retry_zero_rtt_interaction'].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(
        [
            '',
            '## Preserved third-party evidence',
            '',
            '| Scenario | Feature | Artifact dir |',
            '|---|---|---|',
        ]
    )
    for row in payload['evidence']:
        lines.append(f"| `{row['scenario_id']}` | `{row['feature']}` | `{row['artifact_dir']}` |")
    return '\n'.join(lines) + '\n'


def _render_quic_state_md(payload: dict[str, Any]) -> str:
    lines = [
        '# QUIC State Evidence',
        '',
        'This file is generated from the canonical independent HTTP/3 release matrix and the Phase 4 QUIC state-claim metadata.',
        '',
        '| Claim | Title | Scenario | Evidence tier | Notes |',
        '|---|---|---|---|---|',
    ]
    for row in payload['claims']:
        for scenario in row['scenarios']:
            lines.append(
                f"| `{row['claim_id']}` | {row['title']} | `{scenario['scenario_id']}` | `{scenario['evidence_tier']}` | {row['notes']} |"
            )
    return '\n'.join(lines) + '\n'


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


def generate() -> None:
    release_matrix_path = ROOT / 'docs' / 'review' / 'conformance' / 'external_matrix.release.json'
    release_matrix = json.loads(release_matrix_path.read_text(encoding='utf-8'))
    scenario_by_id = {scenario['id']: scenario for scenario in release_matrix['scenarios']}
    release_root = ROOT / 'docs' / 'review' / 'conformance' / 'releases' / '0.3.9' / 'release-0.3.9'
    independent_root = release_root / 'tigrcorn-independent-certification-release-matrix'

    evidence_rows = []
    claim_rows = []
    for claim in QUIC_STATE_CLAIMS:
        scenarios = []
        for scenario_id in claim['scenarios']:
            scenario = scenario_by_id[scenario_id]
            artifact_dir = independent_root / scenario_id
            scenarios.append(
                {
                    'scenario_id': scenario_id,
                    'feature': scenario['feature'],
                    'protocol': scenario['protocol'],
                    'evidence_tier': scenario['evidence_tier'],
                    'peer': scenario['peer'],
                    'artifact_dir': str(artifact_dir.relative_to(ROOT)),
                    'result': str((artifact_dir / 'result.json').relative_to(ROOT)),
                    'summary': str((artifact_dir / 'summary.json').relative_to(ROOT)),
                    'peer_transcript': str((artifact_dir / 'peer_transcript.json').relative_to(ROOT)),
                    'qlog': str((artifact_dir / 'qlog.json').relative_to(ROOT)),
                }
            )
            evidence_rows.append(
                {
                    'claim_id': claim['claim_id'],
                    'scenario_id': scenario_id,
                    'feature': scenario['feature'],
                    'artifact_dir': str(artifact_dir.relative_to(ROOT)),
                }
            )
        claim_rows.append({**claim, 'scenarios': scenarios})

    early_data_payload = {
        'contract_version': 1,
        **EARLY_DATA_CONTRACT,
        'evidence': evidence_rows,
        'canonical_release_root': str(release_root.relative_to(ROOT)),
        'release_matrix': str(release_matrix_path.relative_to(ROOT)),
    }
    quic_state_payload = {
        'surface_version': 1,
        'canonical_release_root': str(release_root.relative_to(ROOT)),
        'release_matrix': str(release_matrix_path.relative_to(ROOT)),
        'claims': claim_rows,
    }

    contracts_path = ROOT / 'docs' / 'review' / 'conformance' / 'flag_contracts.json'
    contracts_payload = json.loads(contracts_path.read_text(encoding='utf-8'))
    contract_rows = {row['contract_id']: row for row in contracts_payload['contracts']}
    parser_rows = _parser_rows()
    contract_rows['quic_early_data_policy']['help_text'] = parser_rows.get('--quic-early-data-policy')
    contract_rows['quic_require_retry']['help_text'] = parser_rows.get('--quic-require-retry')
    contract_rows['quic_max_datagram_size']['help_text'] = parser_rows.get('--quic-max-datagram-size')
    contract_rows['quic_idle_timeout']['help_text'] = parser_rows.get('--quic-idle-timeout')
    contract_rows['quic_early_data_policy']['phase4_contract'] = {
        'claim_ids': [
            'TC-CONTRACT-EARLYDATA-ADMISSION',
            'TC-CONTRACT-EARLYDATA-REPLAY',
            'TC-CONTRACT-EARLYDATA-TOPOLOGY',
            'TC-CONTRACT-EARLYDATA-APP-VISIBILITY',
        ],
        'docs': ['docs/conformance/early_data_contract.md', 'docs/conformance/quic_state.md'],
        'default_policy': EARLY_DATA_CONTRACT['default_policy'],
        'help_parity': True,
        'runtime_parity': True,
    }
    contract_rows['quic_require_retry']['phase4_contract'] = {
        'claim_ids': ['TC-STATE-QUIC-RETRY'],
        'docs': ['docs/conformance/quic_state.md'],
        'help_parity': True,
        'runtime_parity': True,
    }
    contracts_payload['phase4_review'] = {
        'reviewed': True,
        'early_data_doc': 'docs/conformance/early_data_contract.md',
        'early_data_json': 'docs/conformance/early_data_contract.json',
        'quic_state_doc': 'docs/conformance/quic_state.md',
        'quic_state_json': 'docs/conformance/quic_state.json',
        'claim_count': len(QUIC_STATE_CLAIMS),
    }
    _write_json(contracts_path, contracts_payload)

    _write_json(ROOT / 'docs' / 'conformance' / 'early_data_contract.json', early_data_payload)
    _write_json(ROOT / 'docs' / 'conformance' / 'quic_state.json', quic_state_payload)
    (ROOT / 'docs' / 'conformance' / 'early_data_contract.md').write_text(_render_early_data_md(early_data_payload), encoding='utf-8')
    (ROOT / 'docs' / 'conformance' / 'quic_state.md').write_text(_render_quic_state_md(quic_state_payload), encoding='utf-8')
    (ROOT / 'docs' / 'review' / 'conformance' / 'cli_help.current.txt').write_text(build_parser().format_help(), encoding='utf-8')


if __name__ == '__main__':
    generate()
