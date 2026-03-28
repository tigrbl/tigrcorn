from __future__ import annotations

import json
from pathlib import Path

from tigrcorn.compat.release_gates import evaluate_release_gates, validate_independent_certification_bundle

ROOT = Path(__file__).resolve().parents[1]
CONFORMANCE = ROOT / 'docs' / 'review' / 'conformance'
RELEASE_ROOT = CONFORMANCE / 'releases' / '0.3.9' / 'release-0.3.9'
INDEPENDENT = RELEASE_ROOT / 'tigrcorn-independent-certification-release-matrix'
LOCAL_BEHAVIOR = RELEASE_ROOT / 'tigrcorn-trailer-fields-local-behavior-artifacts'


def _load_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def test_phase9d2_docs_and_status_exist() -> None:
    assert (CONFORMANCE / 'PHASE9D2_TRAILER_FIELDS_INDEPENDENT_CLOSURE.md').exists()
    assert (CONFORMANCE / 'phase9d2_trailer_fields_independent.current.json').exists()
    assert (CONFORMANCE / 'TRAILER_FIELDS_LOCAL_BEHAVIOR_ARTIFACTS.md').exists()
    assert (CONFORMANCE / 'trailer_fields_local_behavior_artifacts.current.json').exists()
    assert (ROOT / 'DELIVERY_NOTES_PHASE9D2_TRAILER_FIELDS_INDEPENDENT_CLOSURE.md').exists()

    payload = _load_json(CONFORMANCE / 'phase9d2_trailer_fields_independent.current.json')
    assert payload['phase'] == '9D2'
    assert payload['status'] == 'trailer_fields_independent_closure_complete_all_carriers_green'
    assert payload['current_state']['authoritative_boundary_passed'] is True
    assert payload['current_state']['strict_target_boundary_passed'] is True
    assert payload['current_state']['promotion_target_passed'] is True
    assert payload['current_state']['strict_failure_count'] == 0
    assert payload['current_state']['non_passing_independent_scenarios'] == []


def test_phase9d2_release_root_contains_trailer_artifacts_and_local_behavior_bundle() -> None:
    index_payload = _load_json(INDEPENDENT / 'index.json')
    entries = {entry['id']: entry for entry in index_payload['scenarios']}
    assert entries['http11-trailer-fields-curl-client']['passed'] is True
    assert entries['http2-trailer-fields-h2-client']['passed'] is True
    assert entries['http3-trailer-fields-aioquic-client']['passed'] is True

    h1_result = _load_json(INDEPENDENT / 'http11-trailer-fields-curl-client' / 'result.json')
    assert h1_result['passed'] is True
    assert h1_result['transcript']['peer']['response']['body'] == 'ok'
    assert h1_result['transcript']['peer']['response']['trailers'] == [['x-trailer-one', 'yes'], ['x-trailer-two', 'done']]

    h2_result = _load_json(INDEPENDENT / 'http2-trailer-fields-h2-client' / 'result.json')
    assert h2_result['passed'] is True
    assert h2_result['transcript']['peer']['response']['body'] == 'ok'
    assert h2_result['transcript']['peer']['response']['trailers'] == [['x-trailer-one', 'yes'], ['x-trailer-two', 'done']]
    assert h2_result['transcript']['peer']['response']['stream_ended'] is True

    h3_result = _load_json(INDEPENDENT / 'http3-trailer-fields-aioquic-client' / 'result.json')
    assert h3_result['passed'] is True
    assert h3_result['peer']['exit_code'] == 0
    assert h3_result['negotiation']['peer']['protocol'] == 'h3'
    for name in ['sut_transcript', 'peer_transcript', 'sut_negotiation', 'peer_negotiation']:
        assert h3_result['artifacts'][name]['exists'] is True

    local_index = _load_json(LOCAL_BEHAVIOR / 'index.json')
    assert {entry['id'] for entry in local_index['scenarios']} == {
        'http11-request-trailers-pass',
        'http11-request-trailers-drop',
        'http11-request-trailers-strict-invalid',
        'http11-response-trailers-pass',
        'http2-request-trailers-pass',
        'http2-request-trailers-strict-invalid',
        'http2-response-trailers-pass',
        'http3-request-trailers-pass',
        'http3-request-trailers-strict-invalid',
        'http3-response-trailers-pass',
    }
    assert local_index['failed'] == 0


def test_phase9d2_strict_boundary_tracks_trailer_progress_in_0_3_8_root() -> None:
    boundary = _load_json(CONFORMANCE / 'certification_boundary.strict_target.json')
    assert boundary['canonical_release_bundle'] == 'docs/review/conformance/releases/0.3.9/release-0.3.9'
    assert boundary['artifact_bundles']['independent_certification'].endswith('releases/0.3.9/release-0.3.9/tigrcorn-independent-certification-release-matrix')

    report = evaluate_release_gates(ROOT, boundary_path='docs/review/conformance/certification_boundary.strict_target.json')
    failures = '\n'.join(report.failures)
    assert report.passed is True
    assert 'RFC 9110 §6.5 independent_certification scenario http3-trailer-fields-aioquic-client has preserved artifacts but they are not marked passing' not in failures
    assert 'RFC 9110 §6.5 independent_certification scenario http11-trailer-fields-curl-client is missing preserved artifacts under the canonical independent release bundle' not in failures
    assert 'RFC 9110 §6.5 independent_certification scenario http2-trailer-fields-h2-client is missing preserved artifacts under the canonical independent release bundle' not in failures
    assert 'RFC 9110 §6.5 references unknown independent_certification scenario http11-trailer-fields-curl-client' not in failures
    assert 'RFC 9110 §6.5 references unknown independent_certification scenario http2-trailer-fields-h2-client' not in failures


def test_phase9d2_independent_bundle_still_validates() -> None:
    report = validate_independent_certification_bundle(INDEPENDENT)
    assert report.passed is True
    assert report.failures == []
