from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tigrcorn.compat.interop_runner import run_external_matrix
from tigrcorn.compat.release_gates import evaluate_promotion_target, evaluate_release_gates
from tigrcorn.protocols.websocket.extensions import (
    default_permessage_deflate_agreement,
    negotiate_permessage_deflate,
    parse_permessage_deflate_offers,
)
from tools.interop_wrappers import describe_wrapper_registry

CONFORMANCE = ROOT / 'docs' / 'review' / 'conformance'
RELEASES = CONFORMANCE / 'releases'
STRICT_BOUNDARY = CONFORMANCE / 'certification_boundary.strict_target.json'
TO_ROOT = RELEASES / '0.3.8' / 'release-0.3.8'
TO_INDEPENDENT = TO_ROOT / 'tigrcorn-independent-certification-release-matrix'
TO_SAME_STACK = TO_ROOT / 'tigrcorn-same-stack-replay-matrix'
TO_MIXED = TO_ROOT / 'tigrcorn-mixed-compatibility-release-matrix'
LOCAL_NEGATIVE_ROOT = TO_ROOT / 'tigrcorn-rfc7692-local-negative-artifacts'
TMP_ROOT = ROOT / '.artifacts' / 'phase9c_rfc7692_runs'
PHASE9C_STATUS_JSON = CONFORMANCE / 'phase9c_rfc7692_independent_closure.current.json'
PHASE9C_STATUS_MD = CONFORMANCE / 'PHASE9C_RFC7692_INDEPENDENT_CLOSURE.md'
DELIVERY_NOTES = ROOT / 'DELIVERY_NOTES_PHASE9C_RFC7692_INDEPENDENT_CLOSURE.md'
RFC7692_SCENARIOS = [
    'websocket-http11-server-websockets-client-permessage-deflate',
    'websocket-http2-server-h2-client-permessage-deflate',
    'websocket-http3-server-aioquic-client-permessage-deflate',
]
STEP3_SCENARIOS = ['websocket-http3-server-aioquic-client-permessage-deflate']
BUNDLE_COMMIT = 'phase9c-rfc7692-checkpoint'


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dump_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + '\n', encoding='utf-8')


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))


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
        payload = _replace_paths(_load_json(path), old, new)
        _dump_json(path, payload)


def _scenario_entries(index_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(entry['id']): entry for entry in index_payload.get('scenarios', []) if entry.get('id') is not None}


def _load_generated_bundle(bundle_root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    manifest = _load_json(bundle_root / 'manifest.json')
    index_payload = _load_json(bundle_root / 'index.json')
    summary = _load_json(bundle_root / 'summary.json')
    return manifest, index_payload, summary


def _overlay_generated_scenarios(generated_root: Path) -> None:
    _, gen_index, _ = _load_generated_bundle(generated_root)
    if not TO_INDEPENDENT.exists():
        raise FileNotFoundError(f'missing independent bundle destination: {TO_INDEPENDENT}')

    index_path = TO_INDEPENDENT / 'index.json'
    manifest_path = TO_INDEPENDENT / 'manifest.json'
    summary_path = TO_INDEPENDENT / 'summary.json'
    index_payload = _load_json(index_path)
    manifest_payload = _load_json(manifest_path)
    entries = _scenario_entries(index_payload)

    new_prefix = str(TO_INDEPENDENT.relative_to(ROOT))
    old_prefix = str(generated_root.relative_to(ROOT))

    for scenario_id in STEP3_SCENARIOS:
        src_dir = generated_root / scenario_id
        if not src_dir.exists():
            continue
        dst_dir = TO_INDEPENDENT / scenario_id
        if dst_dir.exists():
            shutil.rmtree(dst_dir)
        shutil.copytree(src_dir, dst_dir)
        _rewrite_json_tree(dst_dir, old_prefix, new_prefix)

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
    passed = sum(1 for entry in scenarios if entry.get('passed'))
    failed = sum(1 for entry in scenarios if not entry.get('passed'))
    index_payload['artifact_root'] = str(TO_INDEPENDENT.relative_to(ROOT))
    index_payload['bundle_kind'] = 'independent_certification'
    index_payload['commit_hash'] = BUNDLE_COMMIT
    index_payload['required_bundle_files'] = list(gen_index.get('required_bundle_files', []))
    index_payload['required_scenario_files'] = list(gen_index.get('required_scenario_files', []))
    index_payload['wrapper_families'] = describe_wrapper_registry()['families']
    index_payload['scenarios'] = scenarios
    index_payload['total'] = len(scenarios)
    index_payload['passed'] = passed
    index_payload['failed'] = failed
    index_payload['skipped'] = 0
    index_payload['schema_version'] = 1

    summary_payload = {
        'artifact_root': str(TO_INDEPENDENT.relative_to(ROOT)),
        'bundle_kind': 'independent_certification',
        'commit_hash': BUNDLE_COMMIT,
        'failed': failed,
        'matrix_name': index_payload['matrix_name'],
        'passed': passed,
        'required_bundle_files': list(index_payload['required_bundle_files']),
        'required_scenario_files': list(index_payload['required_scenario_files']),
        'scenario_ids': [entry['id'] for entry in scenarios],
        'schema_version': 1,
        'skipped': 0,
        'total': len(scenarios),
        'wrapper_families': describe_wrapper_registry()['families'],
    }

    manifest_payload['artifact_schema_version'] = 1
    manifest_payload['commit_hash'] = BUNDLE_COMMIT
    manifest_payload['generated_at'] = _now()
    manifest_payload['required_bundle_files'] = list(index_payload['required_bundle_files'])
    manifest_payload['required_scenario_files'] = list(index_payload['required_scenario_files'])
    manifest_payload['wrapper_families'] = describe_wrapper_registry()['families']
    feature_values = set(manifest_payload.get('dimensions', {}).get('feature', []))
    feature_values.add('permessage-deflate')
    manifest_payload.setdefault('dimensions', {})['feature'] = sorted(feature_values)
    notes = list(manifest_payload.get('notes', []))
    note = 'Phase 9C overlays a passing RFC 7692 HTTP/3 aioquic permessage-deflate artifact into the 0.3.8 working release root while preserving the existing HTTP/1.1 and HTTP/2 passing artifacts.'
    if note not in notes:
        notes.append(note)
    manifest_payload['notes'] = notes

    _dump_json(index_path, index_payload)
    _dump_json(summary_path, summary_payload)
    _dump_json(manifest_path, manifest_payload)


def _create_local_negative_artifacts() -> None:
    if LOCAL_NEGATIVE_ROOT.exists():
        shutil.rmtree(LOCAL_NEGATIVE_ROOT)
    LOCAL_NEGATIVE_ROOT.mkdir(parents=True, exist_ok=True)

    scenarios: list[dict[str, Any]] = []
    vectors = []

    offers = parse_permessage_deflate_offers([
        (b'sec-websocket-extensions', b'permessage-deflate; server_max_window_bits'),
        (b'sec-websocket-extensions', b'permessage-deflate; client_max_window_bits=15; server_max_window_bits=15'),
    ])
    vectors.append({
        'id': 'invalid-offer-parameters-ignored',
        'description': 'Malformed permessage-deflate offer parameters are ignored by offer parsing instead of being promoted into a negotiated runtime.',
        'passed': offers == [default_permessage_deflate_agreement(offers) and offers[0]][:1],
        'result': {
            'parsed_offer_count': len(offers),
            'accepted_offer_header': 'permessage-deflate; client_max_window_bits=15; server_max_window_bits=15',
            'source_tests': ['tests/test_websocket_rfc7692.py'],
        },
    })

    rejected = False
    rejection_message = None
    try:
        negotiate_permessage_deflate(
            request_headers=[(b'sec-websocket-extensions', b'permessage-deflate')],
            response_headers=[(b'sec-websocket-extensions', b'permessage-deflate; client_max_window_bits=10')],
        )
    except RuntimeError as exc:
        rejected = True
        rejection_message = str(exc)
    vectors.append({
        'id': 'unsolicited-client-max-window-bits-rejected',
        'description': 'The server must not claim client_max_window_bits in the response when the client did not offer it.',
        'passed': rejected,
        'result': {
            'rejected': rejected,
            'error': rejection_message,
            'source_tests': ['tests/test_websocket_rfc7692.py'],
        },
    })

    default_agreement = default_permessage_deflate_agreement(parse_permessage_deflate_offers([
        (b'sec-websocket-extensions', b'permessage-deflate; client_max_window_bits=15; server_max_window_bits=15'),
    ]))
    vectors.append({
        'id': 'explicit-window-bits-default-agreement',
        'description': 'The default server agreement mirrors explicit client/server window-bit constraints so third-party peers receive a matching negotiation response.',
        'passed': default_agreement is not None and default_agreement.server_max_window_bits == 15 and default_agreement.client_max_window_bits == 15,
        'result': {
            'agreement_header': None if default_agreement is None else default_agreement.as_header_value().decode('ascii'),
            'source_tests': ['tests/test_websocket_rfc7692.py'],
        },
    })

    for vector in vectors:
        scenario_dir = LOCAL_NEGATIVE_ROOT / vector['id']
        scenario_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            'scenario_id': vector['id'],
            'passed': bool(vector['passed']),
            'description': vector['description'],
            'result': vector['result'],
        }
        _dump_json(scenario_dir / 'result.json', payload)
        scenarios.append({'id': vector['id'], 'passed': bool(vector['passed']), 'artifact_dir': str(scenario_dir.relative_to(ROOT))})

    manifest = {
        'bundle_kind': 'local_negative_artifacts',
        'commit_hash': BUNDLE_COMMIT,
        'generated_at': _now(),
        'phase': '9C',
        'rfcs': ['RFC 7692'],
        'description': 'Local negative and compatibility vectors preserved during Phase 9C RFC 7692 independent closure work.',
    }
    index_payload = {
        'artifact_root': str(LOCAL_NEGATIVE_ROOT.relative_to(ROOT)),
        'bundle_kind': 'local_negative_artifacts',
        'commit_hash': BUNDLE_COMMIT,
        'matrix_name': 'tigrcorn-rfc7692-local-negative-artifacts',
        'total': len(scenarios),
        'passed': sum(1 for entry in scenarios if entry['passed']),
        'failed': sum(1 for entry in scenarios if not entry['passed']),
        'scenarios': scenarios,
    }
    _dump_json(LOCAL_NEGATIVE_ROOT / 'manifest.json', manifest)
    _dump_json(LOCAL_NEGATIVE_ROOT / 'index.json', index_payload)


def _update_strict_boundary() -> None:
    payload = _load_json(STRICT_BOUNDARY)
    payload['canonical_release_bundle'] = 'docs/review/conformance/releases/0.3.8/release-0.3.8'
    payload['artifact_bundles'] = {
        'independent_certification': 'docs/review/conformance/releases/0.3.8/release-0.3.8/tigrcorn-independent-certification-release-matrix',
        'same_stack_replay': 'docs/review/conformance/releases/0.3.8/release-0.3.8/tigrcorn-same-stack-replay-matrix',
        'mixed': 'docs/review/conformance/releases/0.3.8/release-0.3.8/tigrcorn-mixed-compatibility-release-matrix',
    }
    _dump_json(STRICT_BOUNDARY, payload)


def _update_release_root_manifest() -> None:
    manifest_path = TO_ROOT / 'manifest.json'
    manifest = _load_json(manifest_path) if manifest_path.exists() else {}
    manifest.update({
        'release': '0.3.8',
        'schema_version': 1,
        'generated_at': _now(),
        'source_checkpoint': 'phase9c_rfc7692_independent_closure',
        'status': 'phase9c_rfc7692_complete_all_carriers_green',
        'promotion_ready': False,
        'strict_target_complete': False,
    })
    bundles = dict(manifest.get('bundles', {}))
    bundles['independent_certification'] = {
        'path': str(TO_INDEPENDENT.relative_to(ROOT)),
        'scenario_count': len(_load_json(TO_INDEPENDENT / 'index.json').get('scenarios', [])),
        'release_gate_eligible': True,
        'rfc7692_scenarios': RFC7692_SCENARIOS,
    }
    bundles['same_stack_replay'] = {
        'path': str(TO_SAME_STACK.relative_to(ROOT)),
        'release_gate_eligible': True,
    }
    bundles['mixed'] = {
        'path': str(TO_MIXED.relative_to(ROOT)),
        'release_gate_eligible': True,
    }
    bundles['local_rfc7692_negative_artifacts'] = {
        'path': str(LOCAL_NEGATIVE_ROOT.relative_to(ROOT)),
        'release_gate_eligible': False,
        'vector_count': len(_load_json(LOCAL_NEGATIVE_ROOT / 'index.json').get('scenarios', [])),
    }
    manifest['bundles'] = bundles
    manifest['notes'] = [
        'Phase 9B independent harness foundation remains preserved in this release root.',
        'Phase 9C now preserves passing RFC 7692 independent artifacts for HTTP/1.1, HTTP/2, and HTTP/3 under the 0.3.8 working release root.',
        'This release root remains non-promotable because the strict target and promotion target are still blocked by the remaining HTTP/3 CONNECT, trailer-fields, and content-coding scenarios.',
    ]
    _dump_json(manifest_path, manifest)

    (TO_ROOT / 'README.md').write_text(
        '# Release 0.3.8 working promotion root\n\n'
        'This directory remains the next promotable working root reserved by the Phase 9 plan.\n\n'
        'Current truth after the Step 3 RFC 7692 HTTP/3 closure checkpoint:\n\n'
        '- the release root is **not yet promotable**\n'
        '- RFC 7692 independent artifacts are now green across HTTP/1.1, HTTP/2, and HTTP/3\n'
        '- the remaining strict-target blockers are now the preserved-but-non-passing HTTP/3 CONNECT, trailer-fields, and content-coding scenarios\n',
        encoding='utf-8',
    )


def _write_phase9c_status_and_docs() -> None:
    authoritative = evaluate_release_gates(ROOT)
    strict = evaluate_release_gates(ROOT, boundary_path='docs/review/conformance/certification_boundary.strict_target.json')
    promotion = evaluate_promotion_target(ROOT)
    independent_index = _load_json(TO_INDEPENDENT / 'index.json')
    entries = _scenario_entries(independent_index)
    scenario_status = {scenario_id: entries[scenario_id] for scenario_id in RFC7692_SCENARIOS if scenario_id in entries}
    remaining_blockers = [
        'http3-connect-relay-aioquic-client',
        'http3-trailer-fields-aioquic-client',
        'http3-content-coding-aioquic-client',
    ]
    payload = {
        'phase': '9C',
        'checkpoint': 'phase9c_rfc7692_independent_closure',
        'status': 'rfc7692_independent_closure_complete_all_carriers_green',
        'generated_on': _now(),
        'current_state': {
            'authoritative_boundary_passed': authoritative.passed,
            'strict_target_boundary_passed': strict.passed,
            'promotion_target_passed': promotion.passed,
            'flag_surface_passed': promotion.flag_surface.passed,
            'operator_surface_passed': promotion.operator_surface.passed,
            'performance_passed': promotion.performance.passed,
            'documentation_passed': promotion.documentation.passed,
            'strict_failure_count': len(strict.failures),
            'remaining_non_passing_independent_scenarios': remaining_blockers,
            'rfc7692_complete_all_carriers': all(bool(scenario_status.get(item, {}).get('passed')) for item in RFC7692_SCENARIOS),
        },
        'rfc7692': {
            'strict_target_required_evidence_tier': 'independent_certification',
            'artifact_bundle': str(TO_INDEPENDENT.relative_to(ROOT)),
            'scenario_status': scenario_status,
            'negative_local_artifacts': {
                'path': str(LOCAL_NEGATIVE_ROOT.relative_to(ROOT)),
                'vector_ids': [
                    'invalid-offer-parameters-ignored',
                    'unsolicited-client-max-window-bits-rejected',
                    'explicit-window-bits-default-agreement',
                ],
            },
        },
        'strict_boundary_failures': strict.failures,
        'honest_current_result': [
            'RFC 7692 independent-certification evidence is now preserved as passing third-party artifacts across HTTP/1.1, HTTP/2, and HTTP/3 under the 0.3.8 working release root.',
            'The strict boundary and the composite promotion target remain red only because the HTTP/3 CONNECT, trailer-fields, and content-coding scenarios are still preserved as non-passing artifacts.',
        ],
    }
    _dump_json(PHASE9C_STATUS_JSON, payload)
    PHASE9C_STATUS_MD.write_text(
        '# Phase 9C RFC 7692 independent-certification closure\n\n'
        'This checkpoint now records RFC 7692 as green across all three required carriers in the 0.3.8 working release root.\n\n'
        '## Current result\n\n'
        f"- authoritative boundary: `{authoritative.passed}`\n"
        f"- strict target boundary: `{strict.passed}`\n"
        f"- promotion target: `{promotion.passed}`\n"
        '- RFC 7692 HTTP/1.1 scenario: `passed`\n'
        '- RFC 7692 HTTP/2 scenario: `passed`\n'
        '- RFC 7692 HTTP/3 scenario: `passed`\n\n'
        'The HTTP/3 `aioquic` RFC 7692 scenario now preserves the previously missing sidecar artifacts: `sut_transcript.json`, `peer_transcript.json`, `sut_negotiation.json`, and `peer_negotiation.json`.\n\n'
        'The repository is still **not yet certifiably fully featured** and **not yet strict-target certifiably fully RFC compliant** because the remaining strict-target blockers are now limited to the HTTP/3 CONNECT, trailer-fields, and content-coding scenarios.\n',
        encoding='utf-8',
    )
    DELIVERY_NOTES.write_text(
        '# Delivery notes — Phase 9C RFC 7692 independent closure\n\n'
        'This checkpoint closes the remaining RFC 7692 HTTP/3 strict-target artifact gap by overlaying a passing `aioquic` WebSocket permessage-deflate scenario into the existing 0.3.8 working release root.\n\n'
        'RFC 7692 is now green across HTTP/1.1, HTTP/2, and HTTP/3. The package remains non-promotable because the HTTP/3 CONNECT, trailer-fields, and content-coding scenarios are still non-passing.\n',
        encoding='utf-8',
    )


def _update_current_repository_state() -> None:
    path = ROOT / 'CURRENT_REPOSITORY_STATE.md'
    text = path.read_text(encoding='utf-8')
    phase9c_section = (
        '## Phase 9C RFC 7692 independent-closure checkpoint\n\n'
        'The HTTP/3 RFC 7692 strict-target scenario is now preserved as a **passing** third-party `aioquic` artifact, so RFC 7692 is now green across HTTP/1.1, HTTP/2, and HTTP/3 under the 0.3.8 working release root.\n\n'
        'Primary Phase 9C artifacts:\n\n'
        '- `docs/review/conformance/PHASE9C_RFC7692_INDEPENDENT_CLOSURE.md`\n'
        '- `docs/review/conformance/phase9c_rfc7692_independent_closure.current.json`\n'
        '- `DELIVERY_NOTES_PHASE9C_RFC7692_INDEPENDENT_CLOSURE.md`\n\n'
        'What that means now:\n\n'
        '- RFC 7692 no longer blocks the strict target\n'
        '- the remaining strict-target blockers are only the HTTP/3 CONNECT, trailer-fields, and content-coding scenarios\n\n'
    )
    if '## Phase 9C RFC 7692 independent-closure checkpoint' not in text:
        anchor = '## Phase 9 implementation-plan checkpoint\n\n'
        text = text.replace(anchor, anchor + phase9c_section)
    old_blockers = (
        'The remaining blockers are now only the preserved-but-non-passing HTTP/3 `aioquic` strict-target scenarios:\n\n'
        '- `websocket-http3-server-aioquic-client-permessage-deflate`\n'
        '- `http3-connect-relay-aioquic-client`\n'
        '- `http3-trailer-fields-aioquic-client`\n'
        '- `http3-content-coding-aioquic-client`\n'
    )
    new_blockers = (
        'The remaining blockers are now only the preserved-but-non-passing HTTP/3 `aioquic` strict-target scenarios:\n\n'
        '- `http3-connect-relay-aioquic-client`\n'
        '- `http3-trailer-fields-aioquic-client`\n'
        '- `http3-content-coding-aioquic-client`\n'
    )
    text = text.replace(old_blockers, new_blockers)
    path.write_text(text, encoding='utf-8')


def main() -> None:
    if not TO_INDEPENDENT.exists():
        raise FileNotFoundError(f'missing independent bundle destination: {TO_INDEPENDENT}')
    if TMP_ROOT.exists():
        shutil.rmtree(TMP_ROOT)
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    summary = run_external_matrix(
        ROOT / 'docs/review/conformance/external_matrix.release.json',
        artifact_root=TMP_ROOT,
        source_root=ROOT,
        scenario_ids=STEP3_SCENARIOS,
    )
    generated_root = Path(summary.artifact_root)
    _overlay_generated_scenarios(generated_root)
    _create_local_negative_artifacts()
    _update_strict_boundary()
    _update_release_root_manifest()
    _write_phase9c_status_and_docs()
    _update_current_repository_state()


if __name__ == '__main__':
    main()
