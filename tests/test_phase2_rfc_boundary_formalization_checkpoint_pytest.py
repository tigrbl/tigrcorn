from __future__ import annotations

import json
from pathlib import Path

from tigrcorn.compat.release_gates import evaluate_release_gates, evaluate_promotion_target


ROOT = Path(__file__).resolve().parents[1]
CONFORMANCE = ROOT / 'docs' / 'review' / 'conformance'


def _load(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding='utf-8'))


def test_boundaries_formalize_rfc7232_and_rfc7233() -> None:
    authoritative = _load('docs/review/conformance/certification_boundary.json')
    strict = _load('docs/review/conformance/certification_boundary.strict_target.json')
    corpus = _load('docs/review/conformance/corpus.json')

    for payload in (authoritative, strict):
        assert 'RFC 7232' in payload['required_rfcs']
        assert 'RFC 7233' in payload['required_rfcs']
        assert payload['required_rfc_evidence']['RFC 7232']['highest_required_evidence_tier'] == 'local_conformance'
        assert payload['required_rfc_evidence']['RFC 7233']['highest_required_evidence_tier'] == 'local_conformance'
        assert payload['required_rfc_evidence']['RFC 7232']['declared_evidence']['local_conformance'] == ['http-conditional-requests']
        assert payload['required_rfc_evidence']['RFC 7233']['declared_evidence']['local_conformance'] == ['http-byte-ranges']

    vectors = {entry['name']: entry for entry in corpus['vectors']}
    assert vectors['http-conditional-requests']['rfc'] == '7232'
    assert vectors['http-byte-ranges']['rfc'] == '7233'


def test_current_state_docs_no_longer_describe_rfc7232_or_rfc7233_as_unsupported() -> None:
    audit = _load('docs/review/conformance/http_integrity_caching_signatures_status.current.json')
    applicability = _load('docs/review/conformance/rfc_applicability_and_competitor_status.current.json')

    assert audit['rfc_status']['rfc7232']['current_support'] == 'supported_and_targeted'
    assert audit['rfc_status']['rfc7233']['current_support'] == 'supported_and_targeted'
    assert applicability['rfc_applicability']['rfc7232']['current_support'] == 'targeted_and_supported'
    assert applicability['rfc_applicability']['rfc7233']['current_support'] == 'targeted_and_supported'


def test_release_gates_and_promotion_target_remain_green_after_boundary_formalization() -> None:
    authoritative = evaluate_release_gates(ROOT)
    strict = evaluate_release_gates(ROOT, boundary_path='docs/review/conformance/certification_boundary.strict_target.json')
    promotion = evaluate_promotion_target(ROOT)
    assert authoritative.passed, authoritative.failures
    assert strict.passed, strict.failures
    assert promotion.passed, promotion.failures
