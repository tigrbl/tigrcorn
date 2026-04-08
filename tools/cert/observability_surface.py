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
from tigrcorn.config.observability_surface import observability_surface  # noqa: E402


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


def _render_metrics_md(payload: dict[str, Any]) -> str:
    lines = [
        '# Metrics Schema',
        '',
        'This file is generated from the package-owned Phase 6 observability metadata.',
        '',
    ]
    for family, metrics in payload['metrics_schema']['families'].items():
        lines.extend([f'## {family.title()} counters', ''])
        for metric in metrics:
            metric_type = 'gauge' if metric in payload['metrics_schema']['gauge_metrics'] else 'counter'
            lines.append(f"- `{metric}`: `{metric_type}`")
        lines.append('')
    lines.extend(
        [
            '## Notes',
            '',
        ]
    )
    for key, value in payload['metrics_schema']['notes'].items():
        lines.append(f"- `{key}`: {value}")
    return '\n'.join(lines) + '\n'


def _render_qlog_md(payload: dict[str, Any]) -> str:
    qlog = payload['qlog']
    lines = [
        '# Experimental qlog Contract',
        '',
        'This file is generated from the package-owned Phase 6 observability metadata.',
        '',
        f"- `schema_version`: `{qlog['schema_version']}`",
        f"- `stability`: `{qlog['stability']}`",
        f"- `compatibility`: `{qlog['compatibility']}`",
        f"- `producer`: `{qlog['producer']}`",
        '',
        '## Redaction rules',
        '',
    ]
    for key, value in qlog['redaction_rules'].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(['', '## Versioning', ''])
    for key, value in qlog['versioning'].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(['', '## Experimental markers', ''])
    for key, value in qlog['markers'].items():
        lines.append(f"- `{key}`: `{value}`")
    return '\n'.join(lines) + '\n'


def _render_operator_md(payload: dict[str, Any]) -> str:
    lines = [
        '# Observability Operator Guide',
        '',
        'This file is generated from the package-owned Phase 6 observability metadata and the public CLI parser.',
        '',
        '## Export adapters',
        '',
        '| Flag | Config path | Schema version | Help | Accepted values | Failure behavior |',
        '|---|---|---|---|---|---|',
    ]
    for row in payload['export_adapters']:
        accepted = ', '.join(f'`{item}`' for item in row['accepted_values'])
        lines.append(
            f"| `{row['flag']}` | `{row['config_path']}` | `{row['schema_version']}` | {row.get('help_text') or ''} | {accepted} | {row['failure_behavior']} |"
        )
    lines.extend(
        [
            '',
            '## Frozen behavior',
            '',
            '- Metrics are package-owned names exported from one in-process snapshot model; exporter adapters do not rename counters.',
            '- `--statsd-host` accepts plain `host:port`, `statsd://host:port`, or `dogstatsd://host:port`.',
            '- `--otel-endpoint` accepts `http://` and `https://` collector URLs and emits the declared OTLP-style JSON envelope.',
            '- qlog output is explicitly experimental, versioned, and redacted; it is not a stable compatibility target.',
        ]
    )
    return '\n'.join(lines) + '\n'


def generate() -> None:
    payload = observability_surface()
    parser_rows = _parser_rows()
    for row in payload['export_adapters']:
        row['help_text'] = parser_rows.get(row['flag'])

    contracts_path = ROOT / 'docs' / 'review' / 'conformance' / 'flag_contracts.json'
    contracts_payload = json.loads(contracts_path.read_text(encoding='utf-8'))
    contract_rows = {row['contract_id']: row for row in contracts_payload['contracts']}
    for contract_id in ('statsd_host', 'otel_endpoint'):
        row = contract_rows.get(contract_id)
        if row is None:
            continue
        row['phase6_contract'] = {
            'claim_ids': ['TC-OBS-METRICS-SCHEMA', 'TC-OBS-EXPORT-ADAPTERS', 'TC-OBS-QLOG-EXPERIMENTAL'],
            'docs': ['docs/conformance/metrics_schema.md', 'docs/conformance/qlog_experimental.md', 'docs/ops/observability.md'],
            'help_parity': True,
            'runtime_parity': True,
        }
    contracts_payload['phase6_review'] = {
        'reviewed': True,
        'metrics_schema_doc': 'docs/conformance/metrics_schema.md',
        'metrics_schema_json': 'docs/conformance/metrics_schema.json',
        'qlog_doc': 'docs/conformance/qlog_experimental.md',
        'qlog_json': 'docs/conformance/qlog_experimental.json',
        'operator_doc': 'docs/ops/observability.md',
        'claim_count': 3,
    }
    _write_json(contracts_path, contracts_payload)

    _write_json(ROOT / 'docs' / 'conformance' / 'metrics_schema.json', payload)
    _write_json(ROOT / 'docs' / 'conformance' / 'qlog_experimental.json', payload['qlog'])
    (ROOT / 'docs' / 'conformance' / 'metrics_schema.md').write_text(_render_metrics_md(payload), encoding='utf-8')
    (ROOT / 'docs' / 'conformance' / 'qlog_experimental.md').write_text(_render_qlog_md(payload), encoding='utf-8')
    (ROOT / 'docs' / 'ops' / 'observability.md').write_text(_render_operator_md(payload), encoding='utf-8')
    (ROOT / 'docs' / 'review' / 'conformance' / 'cli_help.current.txt').write_text(build_parser().format_help(), encoding='utf-8')


if __name__ == '__main__':
    generate()
