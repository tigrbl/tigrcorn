from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tigrcorn.compat.interop_runner import (  # noqa: E402
    INTEROP_ARTIFACT_SCHEMA_VERSION,
    INTEROP_BUNDLE_REQUIRED_FILES,
    INTEROP_SCENARIO_REQUIRED_FILES,
    _artifact_metadata,
)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + '\n', encoding='utf-8')


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _meta(path: Path) -> dict[str, Any]:
    payload = _artifact_metadata(path)
    payload['path'] = _relative(path)
    return payload


def _logs_inventory(scenario_dir: Path) -> dict[str, Any]:
    return {
        'sut_stdout': _meta(scenario_dir / 'sut_stdout.log'),
        'sut_stderr': _meta(scenario_dir / 'sut_stderr.log'),
        'peer_stdout': _meta(scenario_dir / 'peer_stdout.log'),
        'peer_stderr': _meta(scenario_dir / 'peer_stderr.log'),
        'sut_transcript': _meta(scenario_dir / 'sut_transcript.json'),
        'peer_transcript': _meta(scenario_dir / 'peer_transcript.json'),
        'sut_negotiation': _meta(scenario_dir / 'sut_negotiation.json'),
        'peer_negotiation': _meta(scenario_dir / 'peer_negotiation.json'),
        'qlog': _meta(scenario_dir / 'qlog.json'),
    }


def _build_artifact_inventory(scenario_dir: Path) -> dict[str, Any]:
    artifact_inventory = {
        name: _meta(scenario_dir / name)
        for name in INTEROP_SCENARIO_REQUIRED_FILES
    }
    artifact_inventory.update(
        {
            'packet_trace.jsonl': _meta(scenario_dir / 'packet_trace.jsonl'),
            'qlog.json': _meta(scenario_dir / 'qlog.json'),
            'sut_stdout.log': _meta(scenario_dir / 'sut_stdout.log'),
            'sut_stderr.log': _meta(scenario_dir / 'sut_stderr.log'),
            'peer_stdout.log': _meta(scenario_dir / 'peer_stdout.log'),
            'peer_stderr.log': _meta(scenario_dir / 'peer_stderr.log'),
            'sut_transcript.json': _meta(scenario_dir / 'sut_transcript.json'),
            'peer_transcript.json': _meta(scenario_dir / 'peer_transcript.json'),
            'sut_negotiation.json': _meta(scenario_dir / 'sut_negotiation.json'),
            'peer_negotiation.json': _meta(scenario_dir / 'peer_negotiation.json'),
        }
    )
    return artifact_inventory


def retrofit_bundle(bundle_root: Path) -> tuple[int, int]:
    index_path = bundle_root / 'index.json'
    summary_path = bundle_root / 'summary.json'
    manifest_path = bundle_root / 'manifest.json'
    index_payload = _load_json(index_path)
    summary_payload = _load_json(summary_path)
    manifest_payload = _load_json(manifest_path)

    retrofitted = 0
    total = 0
    scenarios = []
    for entry in index_payload.get('scenarios', []):
        scenario_id = str(entry.get('id', '')).strip()
        if not scenario_id:
            continue
        total += 1
        scenario_dir = bundle_root / scenario_id
        if not scenario_dir.exists() or not (scenario_dir / 'result.json').exists() or not (scenario_dir / 'scenario.json').exists():
            scenarios.append(entry)
            continue
        result_payload = _load_json(scenario_dir / 'result.json')
        scenario_payload = _load_json(scenario_dir / 'scenario.json')
        missing_required = any(not (scenario_dir / name).exists() for name in INTEROP_SCENARIO_REQUIRED_FILES)
        if missing_required:
            retrofitted += 1

        command_payload = {
            'sut': {
                'command': scenario_payload.get('sut', {}).get('command', []),
                'version_command': scenario_payload.get('sut', {}).get('version_command', []),
                'name': scenario_payload.get('sut', {}).get('name'),
                'adapter': scenario_payload.get('sut', {}).get('adapter'),
            },
            'peer': {
                'command': scenario_payload.get('peer_process', {}).get('command', []),
                'version_command': scenario_payload.get('peer_process', {}).get('version_command', []),
                'name': scenario_payload.get('peer_process', {}).get('name'),
                'adapter': scenario_payload.get('peer_process', {}).get('adapter'),
            },
        }
        env_payload = {
            'sut': dict(scenario_payload.get('sut', {}).get('env', {})),
            'peer': dict(scenario_payload.get('peer_process', {}).get('env', {})),
        }
        versions_payload = {
            'sut': dict(result_payload.get('sut', {}).get('version', {})) if isinstance(result_payload.get('sut'), dict) else {},
            'peer': dict(result_payload.get('peer', {}).get('version', {})) if isinstance(result_payload.get('peer'), dict) else {},
        }
        wire_payload = {
            'packet_trace': _meta(scenario_dir / 'packet_trace.jsonl'),
            'logs': _logs_inventory(scenario_dir),
        }
        protocol = scenario_payload.get('dimensions', {}).get('protocol') or scenario_payload.get('metadata', {}).get('protocol')
        feature = scenario_payload.get('dimensions', {}).get('feature') or scenario_payload.get('metadata', {}).get('feature')
        peer_name = scenario_payload.get('dimensions', {}).get('peer') or scenario_payload.get('peer_process', {}).get('name')
        role = scenario_payload.get('dimensions', {}).get('role') or scenario_payload.get('sut', {}).get('role')
        evidence_tier = scenario_payload.get('evidence_tier', 'independent_certification')
        summary_json = {
            'schema_version': INTEROP_ARTIFACT_SCHEMA_VERSION,
            'scenario_id': scenario_id,
            'protocol': protocol,
            'feature': feature,
            'peer': peer_name,
            'role': role,
            'evidence_tier': evidence_tier,
            'passed': bool(result_payload.get('passed', False)),
            'error': result_payload.get('error'),
            'assertions_failed': list(result_payload.get('assertions_failed', [])),
            'required_files': list(INTEROP_SCENARIO_REQUIRED_FILES),
            'artifact_files': {},
        }
        index_json = {
            'schema_version': INTEROP_ARTIFACT_SCHEMA_VERSION,
            'scenario_id': scenario_id,
            'artifact_dir': _relative(scenario_dir),
            'passed': bool(result_payload.get('passed', False)),
            'error': result_payload.get('error'),
            'required_files': list(INTEROP_SCENARIO_REQUIRED_FILES),
            'artifact_files': {},
            'result_path': _relative(scenario_dir / 'result.json'),
            'summary_path': _relative(scenario_dir / 'summary.json'),
        }
        _write_json(scenario_dir / 'command.json', command_payload)
        _write_json(scenario_dir / 'env.json', env_payload)
        _write_json(scenario_dir / 'versions.json', versions_payload)
        _write_json(scenario_dir / 'wire_capture.json', wire_payload)
        artifact_inventory = _build_artifact_inventory(scenario_dir)
        summary_json['artifact_files'] = artifact_inventory
        index_json['artifact_files'] = artifact_inventory
        _write_json(scenario_dir / 'summary.json', summary_json)
        _write_json(scenario_dir / 'index.json', index_json)
        # refresh in-memory entry to align with result state and current paths
        entry.update(
            {
                'artifact_dir': _relative(scenario_dir),
                'assertions_failed': list(result_payload.get('assertions_failed', [])),
                'error': result_payload.get('error'),
                'id': scenario_id,
                'index_path': _relative(scenario_dir / 'index.json'),
                'passed': bool(result_payload.get('passed', False)),
                'result_path': _relative(scenario_dir / 'result.json'),
                'summary_path': _relative(scenario_dir / 'summary.json'),
            }
        )
        scenarios.append(entry)

    scenarios_sorted = sorted(scenarios, key=lambda item: str(item.get('id', '')))
    passed = sum(1 for item in scenarios_sorted if item.get('passed'))
    failed = sum(1 for item in scenarios_sorted if not item.get('passed'))
    index_payload['scenarios'] = scenarios_sorted
    index_payload['total'] = len(scenarios_sorted)
    index_payload['passed'] = passed
    index_payload['failed'] = failed
    index_payload.setdefault('bundle_kind', 'independent_certification')
    index_payload.setdefault('required_bundle_files', list(INTEROP_BUNDLE_REQUIRED_FILES))
    index_payload.setdefault('required_scenario_files', list(INTEROP_SCENARIO_REQUIRED_FILES))
    summary_payload['scenario_ids'] = [str(item.get('id')) for item in scenarios_sorted]
    summary_payload['total'] = len(scenarios_sorted)
    summary_payload['passed'] = passed
    summary_payload['failed'] = failed
    summary_payload.setdefault('bundle_kind', 'independent_certification')
    summary_payload.setdefault('required_bundle_files', list(INTEROP_BUNDLE_REQUIRED_FILES))
    summary_payload.setdefault('required_scenario_files', list(INTEROP_SCENARIO_REQUIRED_FILES))
    manifest_payload.setdefault('bundle_kind', 'independent_certification')
    manifest_payload['artifact_schema_version'] = INTEROP_ARTIFACT_SCHEMA_VERSION
    manifest_payload['required_bundle_files'] = list(INTEROP_BUNDLE_REQUIRED_FILES)
    manifest_payload['required_scenario_files'] = list(INTEROP_SCENARIO_REQUIRED_FILES)
    _write_json(index_path, index_payload)
    _write_json(summary_path, summary_payload)
    _write_json(manifest_path, manifest_payload)
    return retrofitted, total


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    bundle_root = Path(argv[0]) if argv else ROOT / 'docs' / 'review' / 'conformance' / 'releases' / '0.3.8' / 'release-0.3.8' / 'tigrcorn-independent-certification-release-matrix'
    retrofitted, total = retrofit_bundle(bundle_root)
    print(json.dumps({'bundle_root': _relative(bundle_root), 'retrofitted_scenarios': retrofitted, 'total_scenarios': total}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
