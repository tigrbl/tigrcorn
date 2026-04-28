from __future__ import annotations

import json
from pathlib import Path

from tigrcorn.compat.release_gates import evaluate_release_gates, validate_independent_certification_bundle


ROOT = Path(__file__).resolve().parents[1]
CONFORMANCE = ROOT / 'docs' / 'review' / 'conformance'
RELEASE_ROOT = CONFORMANCE / 'releases' / '0.3.9' / 'release-0.3.9'
INDEPENDENT = RELEASE_ROOT / 'tigrcorn-independent-certification-release-matrix'
LOCAL_NEGATIVE = RELEASE_ROOT / 'tigrcorn-connect-relay-local-negative-artifacts'


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def test_phase9d1_docs_and_status_exist() -> None:
    assert (CONFORMANCE / 'PHASE9D1_CONNECT_RELAY_INDEPENDENT_CLOSURE.md').exists()
    assert (CONFORMANCE / 'phase9d1_connect_relay_independent.current.json').exists()
    assert (ROOT / 'docs/review/conformance/delivery/DELIVERY_NOTES_PHASE9D1_CONNECT_RELAY_INDEPENDENT_CLOSURE.md').exists()

    payload = _load_json(CONFORMANCE / 'phase9d1_connect_relay_independent.current.json')
    assert payload['phase'] == '9D1'
    assert payload['status'] == 'connect_relay_independent_closure_complete_all_carriers_green'
    assert payload['current_state']['authoritative_boundary_passed'] is True
    assert payload['current_state']['strict_target_boundary_passed'] is True
    assert payload['current_state']['promotion_target_passed'] is True
    assert payload['current_state']['independent_bundle_validator_passed'] is True
    assert payload['current_state']['non_passing_independent_scenarios'] == []
    assert payload['current_state']['connect_relay_complete_all_carriers'] is True


def test_phase9d1_release_root_contains_connect_artifacts_and_local_negative_vectors() -> None:
    report = validate_independent_certification_bundle(
        INDEPENDENT,
        required_scenarios=[
            'http11-connect-relay-curl-client',
            'http2-connect-relay-h2-client',
            'http3-connect-relay-aioquic-client',
        ],
    )
    assert report.passed is True
    assert report.failures == []

    index_payload = _load_json(INDEPENDENT / 'index.json')
    entries = {entry['id']: entry for entry in index_payload['scenarios']}
    assert entries['http11-connect-relay-curl-client']['passed'] is True
    assert entries['http2-connect-relay-h2-client']['passed'] is True
    assert entries['http3-connect-relay-aioquic-client']['passed'] is True

    h2_result = _load_json(INDEPENDENT / 'http2-connect-relay-h2-client' / 'result.json')
    assert h2_result['passed'] is True
    assert h2_result['transcript']['peer']['tunnel']['connect_status'] == 200
    assert h2_result['transcript']['peer']['response']['body'].startswith('echo:')

    h3_result = _load_json(INDEPENDENT / 'http3-connect-relay-aioquic-client' / 'result.json')
    assert h3_result['passed'] is True
    assert h3_result['peer']['exit_code'] == 0
    assert h3_result['negotiation']['peer']['protocol'] == 'h3'
    for name in ['sut_transcript', 'peer_transcript', 'sut_negotiation', 'peer_negotiation']:
        assert h3_result['artifacts'][name]['exists'] is True

    local_index = _load_json(LOCAL_NEGATIVE / 'index.json')
    assert {entry['id'] for entry in local_index['scenarios']} == {
        'http11-connect-policy-deny',
        'http11-connect-allowlist-rejection',
        'http2-connect-policy-deny',
        'http2-connect-allowlist-rejection',
        'http3-connect-policy-deny',
        'http3-connect-allowlist-rejection',
    }
    assert local_index['failed'] == 0


def test_phase9d1_strict_boundary_reports_connect_as_partial_artifact_failure_not_unknown_scenarios() -> None:
    report = evaluate_release_gates(ROOT, boundary_path='docs/review/conformance/certification_boundary.strict_target.json')
    failures = '\n'.join(report.failures)
    assert report.passed is True
    assert 'RFC 9110 §9.3.6 independent_certification scenario http3-connect-relay-aioquic-client has preserved artifacts but they are not marked passing' not in failures
    assert 'RFC 9110 §9.3.6 references unknown independent_certification scenario http11-connect-relay-curl-client' not in failures
    assert 'RFC 9110 §9.3.6 references unknown independent_certification scenario http2-connect-relay-h2-client' not in failures
