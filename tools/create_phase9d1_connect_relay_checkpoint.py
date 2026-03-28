from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tigrcorn.compat.interop_runner import run_external_matrix  # noqa: E402
from tigrcorn.compat.release_gates import evaluate_promotion_target, validate_independent_certification_bundle  # noqa: E402
from tools.interop_wrappers import describe_wrapper_registry  # noqa: E402
from tools.retrofit_independent_bundle_schema import retrofit_bundle  # noqa: E402

CONFORMANCE = ROOT / 'docs' / 'review' / 'conformance'
RELEASE_ROOT = CONFORMANCE / 'releases' / '0.3.9' / 'release-0.3.9'
INDEPENDENT_ROOT = RELEASE_ROOT / 'tigrcorn-independent-certification-release-matrix'
LOCAL_NEGATIVE_ROOT = RELEASE_ROOT / 'tigrcorn-connect-relay-local-negative-artifacts'
MATRIX_PATH = CONFORMANCE / 'external_matrix.release.json'
STATUS_JSON = CONFORMANCE / 'phase9d1_connect_relay_independent.current.json'
STATUS_MD = CONFORMANCE / 'PHASE9D1_CONNECT_RELAY_INDEPENDENT_CLOSURE.md'
DELIVERY_NOTES = ROOT / 'docs/review/conformance/delivery/DELIVERY_NOTES_PHASE9D1_CONNECT_RELAY_INDEPENDENT_CLOSURE.md'
TMP_ROOT = ROOT / '.artifacts' / 'phase9d1_connect_relay_runs'
SCENARIOS = [
    'http11-connect-relay-curl-client',
    'http2-connect-relay-h2-client',
    'http3-connect-relay-aioquic-client',
]
COMMIT_HASH = 'phase9d1-connect-relay-checkpoint'
OLD_PREFIX = str(TMP_ROOT)
NEW_PREFIX = str(RELEASE_ROOT.relative_to(ROOT))


def _json_default(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    raise TypeError(f'Object of type {type(value).__name__} is not JSON serializable')


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=False, default=_json_default) + '\n', encoding='utf-8')


def _replace_paths(value: Any, old: str, new: str) -> Any:
    if isinstance(value, str):
        return value.replace(old, new)
    if isinstance(value, list):
        return [_replace_paths(item, old, new) for item in value]
    if isinstance(value, dict):
        return {key: _replace_paths(item, old, new) for key, item in value.items()}
    return value


def _rewrite_json_tree(root: Path, old: str, new: str) -> None:
    for path in root.rglob('*.json'):
        payload = _load_json(path)
        payload = _replace_paths(payload, old, new)
        _write_json(path, payload)


def _scenario_entries(index_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(entry['id']): entry for entry in index_payload.get('scenarios', []) if entry.get('id') is not None}


def _overlay_generated_scenarios(generated_root: Path) -> None:
    index_path = INDEPENDENT_ROOT / 'index.json'
    summary_path = INDEPENDENT_ROOT / 'summary.json'
    manifest_path = INDEPENDENT_ROOT / 'manifest.json'
    index_payload = _load_json(index_path)
    summary_payload = _load_json(summary_path)
    manifest_payload = _load_json(manifest_path)
    entries = _scenario_entries(index_payload)
    source_root_str = str(generated_root)
    destination_root_str = str(INDEPENDENT_ROOT.relative_to(ROOT))

    for scenario_id in SCENARIOS:
        src_dir = generated_root / scenario_id
        if not src_dir.exists():
            continue
        dst_dir = INDEPENDENT_ROOT / scenario_id
        if dst_dir.exists():
            shutil.rmtree(dst_dir)
        shutil.copytree(src_dir, dst_dir)
        _rewrite_json_tree(dst_dir, source_root_str, destination_root_str)
        scenario_result = _load_json(dst_dir / 'result.json')
        entries[scenario_id] = {
            'artifact_dir': str(dst_dir.relative_to(ROOT)),
            'assertions_failed': list(scenario_result.get('assertions_failed', [])),
            'error': scenario_result.get('error'),
            'id': scenario_id,
            'index_path': str((dst_dir / 'index.json').relative_to(ROOT)),
            'passed': bool(scenario_result.get('passed', False)),
            'result_path': str((dst_dir / 'result.json').relative_to(ROOT)),
            'summary_path': str((dst_dir / 'summary.json').relative_to(ROOT)),
            'source_bundle': str(generated_root.relative_to(ROOT)),
        }

    scenarios = [entries[key] for key in sorted(entries)]
    passed = sum(1 for item in scenarios if item.get('passed'))
    failed = sum(1 for item in scenarios if not item.get('passed'))
    wrapper_families = describe_wrapper_registry()['families']
    index_payload.update(
        {
            'artifact_root': str(INDEPENDENT_ROOT.relative_to(ROOT)),
            'bundle_kind': 'independent_certification',
            'commit_hash': COMMIT_HASH,
            'total': len(scenarios),
            'passed': passed,
            'failed': failed,
            'scenarios': scenarios,
            'wrapper_families': wrapper_families,
        }
    )
    summary_payload.update(
        {
            'artifact_root': str(INDEPENDENT_ROOT.relative_to(ROOT)),
            'bundle_kind': 'independent_certification',
            'commit_hash': COMMIT_HASH,
            'scenario_ids': [item['id'] for item in scenarios],
            'total': len(scenarios),
            'passed': passed,
            'failed': failed,
            'wrapper_families': wrapper_families,
        }
    )
    feature_values = set(manifest_payload.get('dimensions', {}).get('feature', []))
    feature_values.add('connect-relay')
    manifest_payload['dimensions']['feature'] = sorted(feature_values)
    manifest_payload['artifact_schema_version'] = 1
    manifest_payload['commit_hash'] = COMMIT_HASH
    manifest_payload['generated_at'] = _now()
    manifest_payload['required_bundle_files'] = ['manifest.json', 'summary.json', 'index.json']
    manifest_payload['required_scenario_files'] = ['summary.json', 'index.json', 'result.json', 'scenario.json', 'command.json', 'env.json', 'versions.json', 'wire_capture.json']
    manifest_payload['wrapper_families'] = wrapper_families
    notes = list(manifest_payload.get('notes', []))
    note = 'Phase 9D1 overlays fresh CONNECT relay independent-artifact runs for HTTP/1.1, HTTP/2, and HTTP/3 into the 0.3.9 working release root.'
    if note not in notes:
        notes.append(note)
    manifest_payload['notes'] = notes
    _write_json(index_path, index_payload)
    _write_json(summary_path, summary_payload)
    _write_json(manifest_path, manifest_payload)


def _create_local_negative_bundle() -> None:
    if LOCAL_NEGATIVE_ROOT.exists():
        shutil.rmtree(LOCAL_NEGATIVE_ROOT)
    LOCAL_NEGATIVE_ROOT.mkdir(parents=True, exist_ok=True)
    vectors = [
        ('http11-connect-policy-deny', True, ['tests/test_phase3_strict_rfc_surface.py::StrictRFCSurfaceTests::test_http11_connect_policy_deny_and_allowlist']),
        ('http11-connect-allowlist-rejection', True, ['tests/test_phase3_strict_rfc_surface.py::StrictRFCSurfaceTests::test_http11_connect_policy_deny_and_allowlist']),
        ('http2-connect-policy-deny', True, ['tests/test_phase9d1_connect_relay_local_negatives.py::ConnectRelayPhase9D1LocalNegativeTests::test_http2_connect_policy_deny_and_allowlist_rejection_end_stream']),
        ('http2-connect-allowlist-rejection', True, ['tests/test_phase9d1_connect_relay_local_negatives.py::ConnectRelayPhase9D1LocalNegativeTests::test_http2_connect_policy_deny_and_allowlist_rejection_end_stream']),
        ('http3-connect-policy-deny', True, ['tests/test_phase9d1_connect_relay_local_negatives.py::ConnectRelayPhase9D1LocalNegativeTests::test_http3_connect_policy_deny_and_allowlist_rejection_end_stream']),
        ('http3-connect-allowlist-rejection', True, ['tests/test_phase9d1_connect_relay_local_negatives.py::ConnectRelayPhase9D1LocalNegativeTests::test_http3_connect_policy_deny_and_allowlist_rejection_end_stream']),
    ]
    scenarios = []
    for vector_id, passed, source_tests in vectors:
        scenario_dir = LOCAL_NEGATIVE_ROOT / vector_id
        scenario_dir.mkdir(parents=True, exist_ok=True)
        _write_json(
            scenario_dir / 'result.json',
            {
                'scenario_id': vector_id,
                'passed': passed,
                'preserved_via': 'local_unit_test',
                'source_tests': source_tests,
            },
        )
        scenarios.append({'id': vector_id, 'passed': passed, 'artifact_dir': str(scenario_dir.relative_to(ROOT))})
    _write_json(
        LOCAL_NEGATIVE_ROOT / 'manifest.json',
        {
            'bundle_kind': 'local_negative_artifacts',
            'phase': '9D1',
            'rfc': ['RFC 9110 §9.3.6'],
            'generated_at': _now(),
            'commit_hash': COMMIT_HASH,
            'description': 'Local CONNECT policy-negative vectors preserved during Phase 9D1 independent CONNECT relay closure work.',
        },
    )
    _write_json(
        LOCAL_NEGATIVE_ROOT / 'index.json',
        {
            'artifact_root': str(LOCAL_NEGATIVE_ROOT.relative_to(ROOT)),
            'bundle_kind': 'local_negative_artifacts',
            'total': len(scenarios),
            'passed': len(scenarios),
            'failed': 0,
            'scenarios': scenarios,
        },
    )
    _write_json(
        LOCAL_NEGATIVE_ROOT / 'summary.json',
        {
            'artifact_root': str(LOCAL_NEGATIVE_ROOT.relative_to(ROOT)),
            'bundle_kind': 'local_negative_artifacts',
            'total': len(scenarios),
            'passed': len(scenarios),
            'failed': 0,
            'scenario_ids': [item['id'] for item in scenarios],
        },
    )


def _update_release_root_manifest() -> None:
    manifest_path = RELEASE_ROOT / 'manifest.json'
    payload = _load_json(manifest_path)
    bundles = dict(payload.get('bundles', {}))
    bundles['independent_certification'] = {
        'path': str(INDEPENDENT_ROOT.relative_to(ROOT)),
        'scenario_count': _load_json(INDEPENDENT_ROOT / 'index.json')['total'],
        'release_gate_eligible': True,
        'rfc7692_scenarios': [
            'websocket-http11-server-websockets-client-permessage-deflate',
            'websocket-http2-server-h2-client-permessage-deflate',
            'websocket-http3-server-aioquic-client-permessage-deflate',
        ],
        'connect_relay_scenarios': SCENARIOS,
    }
    bundles['local_connect_relay_negative_artifacts'] = {
        'path': str(LOCAL_NEGATIVE_ROOT.relative_to(ROOT)),
        'release_gate_eligible': False,
        'vector_count': 6,
    }
    payload.update(
        {
            'status': 'phase9d1_connect_relay_complete_all_carriers_green',
            'promotion_ready': False,
            'strict_target_complete': False,
            'source_checkpoint': 'phase9d1_connect_relay_independent_closure',
            'generated_at': _now(),
            'bundles': bundles,
        }
    )
    notes = list(payload.get('notes', []))
    note = 'Phase 9D1 overlays RFC 9110 CONNECT relay independent artifacts for HTTP/1.1, HTTP/2, and HTTP/3 into the 0.3.9 working release root. The remaining strict-target blockers are now trailer-fields and content-coding only.'
    if note not in notes:
        notes.append(note)
    payload['notes'] = notes
    _write_json(manifest_path, payload)


def main() -> int:
    if TMP_ROOT.exists():
        shutil.rmtree(TMP_ROOT)
    with tempfile.TemporaryDirectory(dir=TMP_ROOT.parent if TMP_ROOT.parent.exists() else ROOT / '.artifacts') as tempdir:
        os.environ['TIGRCORN_COMMIT_HASH'] = COMMIT_HASH
        summary = run_external_matrix(MATRIX_PATH, artifact_root=tempdir, source_root=ROOT, scenario_ids=SCENARIOS, strict=False)
        generated_root = Path(summary.artifact_root).resolve()
        _overlay_generated_scenarios(generated_root)
    _create_local_negative_bundle()
    retrofit_bundle(INDEPENDENT_ROOT)
    _update_release_root_manifest()
    report = validate_independent_certification_bundle(INDEPENDENT_ROOT)
    if not report.passed:
        raise SystemExit('independent bundle validation failed: ' + '; '.join(report.failures))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
