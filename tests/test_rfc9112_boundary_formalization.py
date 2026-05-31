from __future__ import annotations

import json
from pathlib import Path

from tigrcorn.compat.release_gates import evaluate_release_gates, evaluate_promotion_target


ROOT = Path(__file__).resolve().parents[1]


def _load(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding='utf-8'))


def test_boundaries_formalize_rfc9112_http11_support() -> None:
    authoritative = _load('docs/review/conformance/certification_boundary.json')
    strict = _load('docs/review/conformance/certification_boundary.strict_target.json')

    for payload in (authoritative, strict):
        assert 'RFC 9112' in payload['required_rfcs']
        assert payload['required_rfc_evidence']['RFC 9112']['highest_required_evidence_tier'] == 'independent_certification'
        assert payload['required_rfc_evidence']['RFC 9112']['declared_evidence']['local_conformance'] == ['http11-server-surface']
        assert payload['required_rfc_evidence']['RFC 9112']['declared_evidence']['independent_certification'] == [
            'http1-server-curl-client'
        ]


def test_release_gates_and_promotion_target_remain_green_after_rfc9112_formalization() -> None:
    authoritative = evaluate_release_gates(ROOT)
    strict = evaluate_release_gates(ROOT, boundary_path='docs/review/conformance/certification_boundary.strict_target.json')
    promotion = evaluate_promotion_target(ROOT)
    assert authoritative.passed, authoritative.failures
    assert strict.passed, strict.failures
    assert promotion.passed, promotion.failures
