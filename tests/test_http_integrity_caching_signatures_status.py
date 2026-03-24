from __future__ import annotations

import json
from pathlib import Path


def test_http_integrity_caching_signatures_status_document_exists() -> None:
    root = Path(__file__).resolve().parents[1]
    report = root / 'docs' / 'review' / 'conformance' / 'http_integrity_caching_signatures_status.current.json'
    assert report.exists(), 'expected focused HTTP integrity/caching/signatures status JSON to exist'

    data = json.loads(report.read_text())
    assert data['checkpoint'] == 'http_integrity_caching_signatures_audit'

    assert data['summary']['authoritative_boundary_certifiably_fully_rfc_compliant'] is True
    assert data['summary']['requested_http_integrity_caching_signatures_stack_fully_supported'] is False
    assert data['summary']['requested_http_integrity_caching_signatures_stack_fully_targeted'] is False

    rfc_status = data['rfc_status']
    assert rfc_status['rfc9110']['current_support'] == 'partially_supported'
    assert rfc_status['rfc9110']['targeted_by_authoritative_boundary'] is True
    assert rfc_status['rfc7232']['current_support'] == 'not_supported'
    assert rfc_status['rfc9111']['current_support'] == 'not_supported'
    assert rfc_status['rfc9530']['current_support'] == 'not_supported'
    assert rfc_status['rfc9421']['current_support'] == 'not_supported'
    assert rfc_status['rfc7515']['current_support'] == 'not_supported'
    assert rfc_status['rfc8152']['current_support'] == 'not_supported'

    feature_status = data['feature_status']
    assert feature_status['accept_encoding']['current_support'] == 'supported'
    assert feature_status['content_encoding']['current_support'] == 'supported'
    assert feature_status['vary']['current_support'] == 'supported_for_content_coding'
    assert feature_status['etag']['current_support'] == 'header-name-only'
    assert feature_status['if_none_match']['current_support'] == 'header-name-only'
    assert feature_status['response_304']['current_support'] == 'generic_status_only'
    assert feature_status['content_digest']['current_support'] == 'not_supported'
    assert feature_status['repr_digest']['current_support'] == 'not_supported'
    assert feature_status['http_signatures']['current_support'] == 'not_supported'
