from __future__ import annotations

import json
from pathlib import Path

from tigrcorn.compat.release_gates import evaluate_release_gates, validate_independent_certification_bundle

ROOT = Path(__file__).resolve().parents[1]
CONFORMANCE = ROOT / 'docs' / 'review' / 'conformance'
RELEASE_ROOT = CONFORMANCE / 'releases' / '0.3.8' / 'release-0.3.8'
INDEPENDENT = RELEASE_ROOT / 'tigrcorn-independent-certification-release-matrix'
LOCAL_BEHAVIOR = RELEASE_ROOT / 'tigrcorn-content-coding-local-behavior-artifacts'


def _load_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def test_phase9d3_docs_and_status_exist() -> None:
    assert (CONFORMANCE / 'PHASE9D3_CONTENT_CODING_INDEPENDENT_CLOSURE.md').exists()
    assert (CONFORMANCE / 'phase9d3_content_coding_independent.current.json').exists()
    assert (CONFORMANCE / 'CONTENT_CODING_LOCAL_BEHAVIOR_ARTIFACTS.md').exists()
    assert (CONFORMANCE / 'content_coding_local_behavior_artifacts.current.json').exists()
    assert (ROOT / 'DELIVERY_NOTES_PHASE9D3_CONTENT_CODING_INDEPENDENT_CLOSURE.md').exists()

    payload = _load_json(CONFORMANCE / 'phase9d3_content_coding_independent.current.json')
    assert payload['phase'] == '9D3'
    assert payload['status'] == 'content_coding_independent_complete_all_carriers_green'
    assert payload['current_state']['authoritative_boundary_passed'] is True
    assert payload['current_state']['strict_target_boundary_passed'] is True
    assert payload['current_state']['promotion_target_passed'] is True
    assert payload['current_state']['non_passing_independent_scenarios'] == []


def test_phase9d3_release_root_contains_content_coding_artifacts_and_local_behavior_bundle() -> None:
    index_payload = _load_json(INDEPENDENT / 'index.json')
    entries = {entry['id']: entry for entry in index_payload['scenarios']}
    assert entries['http11-content-coding-curl-client']['passed'] is True
    assert entries['http2-content-coding-curl-client']['passed'] is True
    assert entries['http3-content-coding-aioquic-client']['passed'] is True

    h1_result = _load_json(INDEPENDENT / 'http11-content-coding-curl-client' / 'result.json')
    assert h1_result['passed'] is True
    assert h1_result['transcript']['peer']['response']['content_encoding'] == 'gzip'
    assert h1_result['transcript']['peer']['response']['decoded_body'] == 'compress-me'
    assert h1_result['transcript']['peer']['response']['vary'] == 'accept-encoding'

    h2_result = _load_json(INDEPENDENT / 'http2-content-coding-curl-client' / 'result.json')
    assert h2_result['passed'] is True
    assert h2_result['transcript']['peer']['response']['content_encoding'] == 'gzip'
    assert h2_result['transcript']['peer']['response']['decoded_body'] == 'compress-me'
    assert h2_result['transcript']['peer']['response']['vary'] == 'accept-encoding'
    assert h2_result['transcript']['peer']['response']['stream_ended'] is True

    h3_result = _load_json(INDEPENDENT / 'http3-content-coding-aioquic-client' / 'result.json')
    assert h3_result['passed'] is True
    assert h3_result['peer']['exit_code'] == 0
    assert h3_result['transcript']['peer']['response']['content_encoding'] == 'gzip'
    assert h3_result['transcript']['peer']['response']['decoded_body'] == 'compress-me'
    assert h3_result['transcript']['peer']['response']['vary'] == 'accept-encoding'

    local_index = _load_json(LOCAL_BEHAVIOR / 'index.json')
    assert {entry['id'] for entry in local_index['scenarios']} == {
        'http11-content-coding-gzip-pass',
        'http11-content-coding-identity-forbidden-406',
        'http11-content-coding-strict-unsupported-406',
        'http2-content-coding-gzip-pass',
        'http2-content-coding-identity-forbidden-406',
        'http2-content-coding-strict-unsupported-406',
        'http3-content-coding-gzip-pass',
        'http3-content-coding-identity-forbidden-406',
        'http3-content-coding-strict-unsupported-406',
    }
    assert local_index['failed'] == 0


def test_phase9d3_strict_boundary_tracks_content_coding_progress_in_0_3_8_root() -> None:
    boundary = _load_json(CONFORMANCE / 'certification_boundary.strict_target.json')
    assert boundary['canonical_release_bundle'] == 'docs/review/conformance/releases/0.3.8/release-0.3.8'
    assert boundary['artifact_bundles']['independent_certification'].endswith('releases/0.3.8/release-0.3.8/tigrcorn-independent-certification-release-matrix')

    report = evaluate_release_gates(ROOT, boundary_path='docs/review/conformance/certification_boundary.strict_target.json')
    failures = '\n'.join(report.failures)
    assert report.passed is True
    assert failures == ''
    assert 'RFC 9110 §8 independent_certification scenario http11-content-coding-curl-client is missing preserved artifacts under the canonical independent release bundle' not in failures
    assert 'RFC 9110 §8 independent_certification scenario http2-content-coding-curl-client is missing preserved artifacts under the canonical independent release bundle' not in failures
    assert 'RFC 9110 §8 references unknown independent_certification scenario http11-content-coding-curl-client' not in failures
    assert 'RFC 9110 §8 references unknown independent_certification scenario http2-content-coding-curl-client' not in failures


def test_phase9d3_independent_bundle_still_validates() -> None:
    report = validate_independent_certification_bundle(INDEPENDENT)
    assert report.passed is True
    assert report.failures == []
