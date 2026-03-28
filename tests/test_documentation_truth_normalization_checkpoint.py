from __future__ import annotations

import json
from pathlib import Path

from tigrcorn.compat.release_gates import evaluate_release_gates, evaluate_promotion_target

ROOT = Path(__file__).resolve().parents[1]


def _load(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding='utf-8'))


def test_canonical_current_state_chain_exists_and_is_explicit() -> None:
    payload = _load('docs/review/conformance/current_state_chain.current.json')
    assert payload['document_role'] == 'canonical_current_state_source'
    assert payload['current_truth_source'] is True
    assert payload['exit_criteria']['one_canonical_current_state_chain'] is True
    assert 'docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md' in payload['canonical_human_current_state_chain']
    assert 'docs/review/conformance/package_compliance_review_phase9i.current.json' in payload['canonical_machine_current_state_chain']
    assert payload['example_path_policy']['canonical_current_phase4_example_tree'] == 'examples/advanced_delivery/'
    assert payload['example_path_policy']['retained_archival_feature_specific_tree'] == 'examples/advanced_protocol_delivery/'


def test_scoped_current_audits_are_non_canonical() -> None:
    for rel in [
        'docs/review/conformance/http_integrity_caching_signatures_status.current.json',
        'docs/review/conformance/rfc_applicability_and_competitor_status.current.json',
        'docs/review/conformance/rfc_applicability_and_competitor_support.current.json',
    ]:
        payload = _load(rel)
        assert payload['document_role'] == 'scoped_current_audit_not_package_wide_truth_source'
        assert payload['current_truth_source'] is False
        assert payload['canonical_current_state_chain'] == 'docs/review/conformance/current_state_chain.current.json'


def test_archival_current_aliases_are_labeled() -> None:
    for rel in [
        'docs/review/conformance/phase1_surface_parity_checkpoint.current.json',
        'docs/review/conformance/phase4_advanced_protocol_delivery_checkpoint.current.json',
        'docs/review/conformance/phase9a_promotion_contract.current.json',
        'docs/review/conformance/promotion_artifact_reconciliation_checkpoint.current.json',
        'docs/review/conformance/documentation_truth_normalization_checkpoint.current.json',
    ]:
        payload = _load(rel)
        assert payload['document_role'] == 'archival_named_current_snapshot_for_stability'
        assert payload['current_truth_source'] is False


def test_example_path_docs_are_normalized() -> None:
    examples_readme = (ROOT / 'examples' / 'README.md').read_text(encoding='utf-8')
    advanced_protocol_readme = (ROOT / 'examples' / 'advanced_protocol_delivery' / 'README.md').read_text(encoding='utf-8')
    pairing = (ROOT / 'examples' / 'PHASE4_PROTOCOL_PAIRING.md').read_text(encoding='utf-8')
    archival_matrix = _load('docs/review/conformance/phase4_advanced_protocol_delivery/example_matrix.json')
    current_matrix = _load('docs/review/conformance/phase4_advanced_delivery/examples_matrix.json')
    assert 'examples/advanced_delivery/' in examples_readme
    assert 'examples/advanced_protocol_delivery/' in examples_readme
    assert 'canonical current integrated Phase 4 example tree' in advanced_protocol_readme
    assert 'canonical integrated example tree' in pairing
    assert archival_matrix['document_role'] == 'archival_phase4_checkpoint_example_matrix'
    assert archival_matrix['current_truth_source'] is False
    assert current_matrix['document_role'] == 'current_subsystem_truth_source'
    assert current_matrix['current_truth_source'] is True


def test_package_review_and_current_state_record_normalization() -> None:
    review = _load('docs/review/conformance/package_compliance_review_phase9i.current.json')
    current = (ROOT / 'docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md').read_text(encoding='utf-8')
    assert review['summary']['documentation_truth_normalized'] is True
    assert review['summary']['canonical_current_state_chain_defined'] is True
    assert review['summary']['historical_current_aliases_labeled'] is True
    assert review['summary']['canonical_phase4_example_tree'] == 'examples/advanced_delivery/'
    assert 'Canonical current-state chain' in current


def test_release_gates_and_promotion_remain_green_after_doc_truth_normalization() -> None:
    authoritative = evaluate_release_gates(ROOT)
    strict = evaluate_release_gates(ROOT, boundary_path='docs/review/conformance/certification_boundary.strict_target.json')
    promotion = evaluate_promotion_target(ROOT)
    assert authoritative.passed, authoritative.failures
    assert strict.passed, strict.failures
    assert promotion.passed, promotion.failures
