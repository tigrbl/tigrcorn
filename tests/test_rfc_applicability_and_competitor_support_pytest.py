from __future__ import annotations

import json
from pathlib import Path


def test_rfc_applicability_and_competitor_support_document_exists() -> None:
    root = Path(__file__).resolve().parents[1]
    report = root / 'docs' / 'review' / 'conformance' / 'rfc_applicability_and_competitor_support.current.json'
    assert report.exists(), 'expected RFC applicability / competitor support JSON to exist'

    data = json.loads(report.read_text())
    assert data['checkpoint'] == 'phase8_rfc_applicability_competitor_support_update'

    summary = data['summary']
    assert summary['first_priority_is_strict_current_target_closure'] is True
    assert summary['core_applicable_rfcs_from_user_table'] == ['rfc9112', 'rfc9113', 'rfc9114', 'rfc9110_bounded', 'rfc7232', 'rfc7233', 'rfc8297', 'rfc7838_section3']
    assert summary['adjacent_optional_expansion_rfcs'] == ['rfc9530']
    assert summary['conditional_boundary_expansion_rfcs'] == ['rfc9111', 'rfc9421']
    assert 'rfc7515' in summary['separate_boundary_optional_rfcs']

    applicability = data['applicability']
    assert applicability['rfc9112']['applicability'] == 'core_transport'
    assert applicability['rfc9110']['applicability'] == 'core_but_bounded'
    assert applicability['rfc7232']['applicability'] == 'core_entity_semantics'
    assert applicability['rfc7232']['current_state'] == 'targeted_and_release_gated_local_conformance'
    assert applicability['rfc7233']['applicability'] == 'core_entity_semantics'
    assert applicability['rfc9111']['applicability'] == 'conditional_expansion'
    assert applicability['rfc9421']['applicability'] == 'conditional_expansion'
    assert applicability['rfc7519']['applicability'] == 'separate_auth_crypto_boundary'
    assert applicability['rfc8152']['applicability'] == 'separate_binary_envelope_boundary'

    next_work = data['recommended_next_work']
    assert next_work['strict_current_target_closure'][0] == 'keep the current authoritative / strict / promotion model green'
    assert next_work['boundary_expansion_after_strict_closure'][0] == 'formalize rfc7232 conditional request subsystem as current boundary work (completed)'
    assert next_work['boundary_expansion_after_strict_closure'][1] == 'formalize rfc7233 range request subsystem as current boundary work (completed)'
    assert 'implement rfc9530 content_digest and repr_digest only if integrity fields become a declared product requirement' in next_work['boundary_expansion_after_strict_closure']
    assert 'rfc9218' in summary['transport_adjacent_optional_rfcs']
    assert data['document_role'] == 'scoped_current_audit_not_package_wide_truth_source'
    assert data['current_truth_source'] is False

    competitors = data['public_competitor_support']
    assert competitors['tigrcorn']['rfc7232_rfc7233_first_class_server_feature'] == 'yes'
    assert competitors['uvicorn']['http2'] == 'no_public_current_claim'
    assert competitors['hypercorn']['http3'] == 'optional_draft_via_aioquic'
    assert competitors['daphne']['http2'] == 'yes'
    assert competitors['granian']['http3'] == 'future_direction_not_current_support'
