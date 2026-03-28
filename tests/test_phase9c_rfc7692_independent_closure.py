from __future__ import annotations

import json
from pathlib import Path

from tigrcorn.compat.release_gates import evaluate_release_gates


ROOT = Path(__file__).resolve().parents[1]
CONFORMANCE = ROOT / 'docs' / 'review' / 'conformance'
RELEASE_ROOT = CONFORMANCE / 'releases' / '0.3.9' / 'release-0.3.9'
INDEPENDENT = RELEASE_ROOT / 'tigrcorn-independent-certification-release-matrix'
LOCAL_NEGATIVE = RELEASE_ROOT / 'tigrcorn-rfc7692-local-negative-artifacts'


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def test_phase9c_docs_and_status_exist() -> None:
    assert (CONFORMANCE / 'PHASE9C_RFC7692_INDEPENDENT_CLOSURE.md').exists()
    assert (CONFORMANCE / 'phase9c_rfc7692_independent_closure.current.json').exists()
    assert (ROOT / 'DELIVERY_NOTES_PHASE9C_RFC7692_INDEPENDENT_CLOSURE.md').exists()

    payload = _load_json(CONFORMANCE / 'phase9c_rfc7692_independent_closure.current.json')
    assert payload['phase'] == '9C'
    assert payload['status'] == 'rfc7692_independent_closure_complete_all_carriers_green'
    assert payload['current_state']['authoritative_boundary_passed'] is True
    assert payload['current_state']['strict_target_boundary_passed'] is True
    assert payload['current_state']['promotion_target_passed'] is True
    assert payload['current_state']['strict_failure_count'] == 0
    assert payload['current_state']['remaining_non_passing_independent_scenarios'] == []
    assert payload['current_state']['rfc7692_complete_all_carriers'] is True


def test_phase9c_release_root_contains_passing_rfc7692_artifacts_and_local_negative_vectors() -> None:
    index_payload = _load_json(INDEPENDENT / 'index.json')
    entries = {entry['id']: entry for entry in index_payload['scenarios']}
    assert entries['websocket-http11-server-websockets-client-permessage-deflate']['passed'] is True
    assert entries['websocket-http2-server-h2-client-permessage-deflate']['passed'] is True
    assert entries['websocket-http3-server-aioquic-client-permessage-deflate']['passed'] is True

    h2_result = _load_json(INDEPENDENT / 'websocket-http2-server-h2-client-permessage-deflate' / 'result.json')
    assert h2_result['passed'] is True
    assert h2_result['transcript']['peer']['response']['extension_header'] == 'permessage-deflate; server_max_window_bits=15; client_max_window_bits=15'

    h3_dir = INDEPENDENT / 'websocket-http3-server-aioquic-client-permessage-deflate'
    h3_result = _load_json(h3_dir / 'result.json')
    h3_index = _load_json(h3_dir / 'index.json')
    assert h3_result['passed'] is True
    for name in ['sut_transcript.json', 'peer_transcript.json', 'sut_negotiation.json', 'peer_negotiation.json']:
        assert h3_index['artifact_files'][name]['exists'] is True

    local_index = _load_json(LOCAL_NEGATIVE / 'index.json')
    assert {entry['id'] for entry in local_index['scenarios']} == {
        'invalid-offer-parameters-ignored',
        'unsolicited-client-max-window-bits-rejected',
        'explicit-window-bits-default-agreement',
    }
    assert local_index['failed'] == 0


def test_phase9c_strict_boundary_now_points_to_0_3_8_and_reports_rfc7692_as_complete() -> None:
    boundary = _load_json(CONFORMANCE / 'certification_boundary.strict_target.json')
    assert boundary['canonical_release_bundle'] == 'docs/review/conformance/releases/0.3.9/release-0.3.9'
    assert boundary['artifact_bundles']['independent_certification'].endswith('releases/0.3.9/release-0.3.9/tigrcorn-independent-certification-release-matrix')

    report = evaluate_release_gates(ROOT, boundary_path='docs/review/conformance/certification_boundary.strict_target.json')
    failures = '\n'.join(report.failures)
    assert report.passed is True
    assert 'RFC 7692 independent_certification scenario websocket-http3-server-aioquic-client-permessage-deflate has preserved artifacts but they are not marked passing' not in failures
    assert 'RFC 7692 requires independent_certification evidence, but the resolved evidence only reaches local_conformance' not in failures
    assert 'RFC 7692 references unknown independent_certification scenario websocket-http11-server-websockets-client-permessage-deflate' not in failures
