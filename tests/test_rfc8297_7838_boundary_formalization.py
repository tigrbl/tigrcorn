from __future__ import annotations

import json
from pathlib import Path

from tigrcorn.compat.release_gates import evaluate_release_gates, evaluate_promotion_target


ROOT = Path(__file__).resolve().parents[1]
CONFORMANCE = ROOT / 'docs' / 'review' / 'conformance'


def _load(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding='utf-8'))


def test_boundaries_formalize_rfc8297_and_rfc7838_section3() -> None:
    authoritative = _load('docs/review/conformance/certification_boundary.json')
    strict = _load('docs/review/conformance/certification_boundary.strict_target.json')
    corpus = _load('docs/review/conformance/corpus.json')

    for payload in (authoritative, strict):
        assert 'RFC 8297' in payload['required_rfcs']
        assert 'RFC 7838 §3' in payload['required_rfcs']
        assert payload['required_rfc_evidence']['RFC 8297']['highest_required_evidence_tier'] == 'local_conformance'
        assert payload['required_rfc_evidence']['RFC 7838 §3']['highest_required_evidence_tier'] == 'local_conformance'
        assert payload['required_rfc_evidence']['RFC 8297']['declared_evidence']['local_conformance'] == ['http-early-hints']
        assert payload['required_rfc_evidence']['RFC 7838 §3']['declared_evidence']['local_conformance'] == ['http-alt-svc-header-advertisement']

    vectors = {entry['name']: entry for entry in corpus['vectors']}
    assert vectors['http-early-hints']['rfc'] == '8297'
    assert vectors['http-alt-svc-header-advertisement']['rfc'] == 'RFC 7838 §3'


def test_phase4_support_statements_are_explicit_and_rfc9218_remains_out() -> None:
    early = _load('docs/review/conformance/phase4_advanced_delivery/early_hints_support_statement.json')
    alt = _load('docs/review/conformance/phase4_advanced_delivery/alt_svc_support_statement.json')
    checkpoint = _load('docs/review/conformance/phase4_advanced_protocol_delivery_checkpoint.current.json')

    assert early['certification_boundary']['target_rfc'] == 'RFC 8297'
    assert early['certification_boundary']['support_envelope'] == 'direct_server_103_early_hints'
    assert alt['certification_boundary']['target_rfc'] == 'RFC 7838 §3'
    assert alt['certification_boundary']['support_envelope'] == 'header_field_advertisement_only'
    assert 'RFC 9218 prioritization' in alt['non_targeted_surfaces']
    assert checkpoint['boundary']['authoritative_phase4_rfc_targets'] == ['RFC 8297', 'RFC 7838 §3']
    assert checkpoint['boundary']['rfc9218_targeted'] is False


def test_phase4_current_state_docs_are_explicit_not_ambiguous() -> None:
    applicability = _load('docs/review/conformance/rfc_applicability_and_competitor_status.current.json')
    review = _load('docs/review/conformance/package_compliance_review_phase9i.current.json')

    assert applicability['rfc_applicability']['rfc8297']['status'] == 'core_current_boundary'
    assert applicability['rfc_applicability']['rfc7838']['status'] == 'core_current_boundary_bounded'
    assert applicability['rfc_applicability']['rfc9218']['status'] == 'transport_adjacent_optional'
    assert review['summary']['phase4_rfc_boundary_formalized'] is True
    assert review['summary']['rfc8297_targeted'] is True
    assert review['summary']['rfc7838_section3_targeted'] is True
    assert review['summary']['rfc9218_targeted'] is False


def test_release_gates_and_promotion_target_remain_green_after_phase4_boundary_formalization() -> None:
    authoritative = evaluate_release_gates(ROOT)
    strict = evaluate_release_gates(ROOT, boundary_path='docs/review/conformance/certification_boundary.strict_target.json')
    promotion = evaluate_promotion_target(ROOT)
    assert authoritative.passed, authoritative.failures
    assert strict.passed, strict.failures
    assert promotion.passed, promotion.failures
