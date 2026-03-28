from __future__ import annotations

import json
from pathlib import Path

from tigrcorn.compat.release_gates import evaluate_release_gates, validate_independent_certification_bundle

ROOT = Path(__file__).resolve().parents[1]
CONFORMANCE = ROOT / 'docs' / 'review' / 'conformance'
RELEASE_ROOT = CONFORMANCE / 'releases' / '0.3.9' / 'release-0.3.9'
INDEPENDENT = RELEASE_ROOT / 'tigrcorn-independent-certification-release-matrix'
LOCAL_VALIDATION = RELEASE_ROOT / 'tigrcorn-ocsp-local-validation-artifacts'


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def test_phase9e_docs_and_status_exist() -> None:
    assert (CONFORMANCE / 'PHASE9E_OCSP_INDEPENDENT_CLOSURE.md').exists()
    assert (CONFORMANCE / 'phase9e_ocsp_independent.current.json').exists()
    assert (CONFORMANCE / 'OCSP_LOCAL_VALIDATION_ARTIFACTS.md').exists()
    assert (CONFORMANCE / 'ocsp_local_validation_artifacts.current.json').exists()
    assert (ROOT / 'DELIVERY_NOTES_PHASE9E_OCSP_INDEPENDENT_CLOSURE.md').exists()

    payload = _load_json(CONFORMANCE / 'phase9e_ocsp_independent.current.json')
    assert payload['phase'] == '9E'
    assert payload['status'] == 'ocsp_independent_green_remaining_http3_blockers'
    assert payload['current_state']['authoritative_boundary_passed'] is True
    assert payload['current_state']['strict_target_boundary_passed'] is False
    assert payload['current_state']['strict_failure_count'] == 2
    assert payload['current_state']['remaining_missing_independent_scenarios'] == []
    assert payload['current_state']['non_passing_independent_scenarios'] == [
        'http3-content-coding-aioquic-client',
    ]


def test_phase9e_release_root_contains_passing_ocsp_artifact_and_local_vectors() -> None:
    index_payload = _load_json(INDEPENDENT / 'index.json')
    entries = {entry['id']: entry for entry in index_payload['scenarios']}
    assert entries['tls-server-ocsp-validation-openssl-client']['passed'] is True

    result = _load_json(INDEPENDENT / 'tls-server-ocsp-validation-openssl-client' / 'result.json')
    assert result['passed'] is True
    assert result['peer']['exit_code'] == 0
    assert result['transcript']['peer']['handshake_established'] is True
    assert result['transcript']['peer']['response']['status'] == 200
    assert result['negotiation']['peer']['verification'] == 'OK'
    assert result['ocsp_responder']['good_request_count'] >= 1

    local_index = _load_json(LOCAL_VALIDATION / 'index.json')
    assert {entry['id'] for entry in local_index['scenarios']} == {
        'ocsp-good-response-cache-reuse-client-auth',
        'ocsp-stale-response-require-fails',
        'ocsp-revoked-client-certificate-fails',
        'ocsp-unreachable-soft-fail-vs-require',
    }
    assert local_index['failed'] == 0


def test_phase9e_strict_boundary_and_validator_reflect_ocsp_progress() -> None:
    report = evaluate_release_gates(ROOT, boundary_path='docs/review/conformance/certification_boundary.strict_target.json')
    failures = '\n'.join(report.failures)
    assert report.passed is True
    assert report.failures == []
    assert 'RFC 6960 independent_certification scenario tls-server-ocsp-validation-openssl-client is missing preserved artifacts under the canonical independent release bundle' not in failures
    assert 'RFC 9110 §9.3.6 independent_certification scenario http3-connect-relay-aioquic-client has preserved artifacts but they are not marked passing' not in failures
    assert 'RFC 6960 requires independent_certification evidence, but the resolved evidence only reaches local_conformance' not in failures

    validation = validate_independent_certification_bundle(INDEPENDENT, required_scenarios=['tls-server-ocsp-validation-openssl-client'])
    assert validation.passed is True
    assert validation.failures == []


def test_phase9e_external_matrix_declares_openssl_ocsp_row() -> None:
    matrix = _load_json(CONFORMANCE / 'external_matrix.release.json')
    entries = {entry['id']: entry for entry in matrix['scenarios']}
    row = entries['tls-server-ocsp-validation-openssl-client']
    assert row['peer'] == 'openssl'
    assert row['peer_process']['metadata']['wrapper_id'] == 'openssl.tls_client'
    assert row['sut']['env']['INTEROP_OCSP_MODE'] == 'require'
