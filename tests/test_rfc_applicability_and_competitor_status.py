from __future__ import annotations

import json
from pathlib import Path


def test_rfc_applicability_and_competitor_status_document_exists() -> None:
    root = Path(__file__).resolve().parents[1]
    report = root / 'docs' / 'review' / 'conformance' / 'rfc_applicability_and_competitor_status.current.json'
    assert report.exists(), 'expected RFC applicability / competitor status JSON to exist'

    data = json.loads(report.read_text())
    assert data['checkpoint'] == 'rfc_applicability_and_competitor_status'
    assert data['reviewed_at'] == '2026-03-20'

    summary = data['summary']
    assert summary['current_core_applicable_rfcs'] == [
        'RFC 9112',
        'RFC 9113',
        'RFC 9114',
        'RFC 9110 §9.3.6',
        'RFC 9110 §6.5',
        'RFC 9110 §8',
    ]
    assert summary['recommended_next_rfcs'] == ['RFC 7232', 'RFC 9530']
    assert summary['conditional_rfcs_if_boundary_expands'] == ['RFC 9111', 'RFC 9421']
    assert summary['non_core_product_layer_rfcs'] == ['RFC 7515', 'RFC 7516', 'RFC 7519', 'RFC 8152', 'RFC 9052']
    assert summary['competitor_review_scope'] == ['uvicorn', 'hypercorn', 'daphne', 'granian']

    applicability = data['rfc_applicability']
    assert applicability['rfc9112']['status'] == 'core_current_boundary'
    assert applicability['rfc9112']['current_support'] == 'targeted_and_supported'
    assert applicability['rfc9113']['status'] == 'core_current_boundary'
    assert applicability['rfc9114']['status'] == 'core_current_boundary'
    assert applicability['rfc9110']['status'] == 'core_current_boundary_partial'
    assert applicability['rfc9110']['covered_sections'] == ['§9.3.6', '§6.5', '§8']
    assert applicability['rfc7232']['status'] == 'adjacent_next_recommended'
    assert applicability['rfc7232']['current_support'] == 'not_supported'
    assert applicability['rfc9530']['status'] == 'adjacent_next_recommended'
    assert applicability['rfc9111']['status'] == 'conditional_boundary_expansion'
    assert applicability['rfc9421']['status'] == 'conditional_boundary_expansion'
    for key in ['rfc7515', 'rfc7516', 'rfc7519', 'rfc8152', 'rfc9052']:
        assert applicability[key]['status'] == 'non_core_product_layer'
        assert applicability[key]['current_support'] == 'not_supported'

    roadmap = data['recommended_roadmap']
    assert [entry['order'] for entry in roadmap] == [1, 2, 3, 4, 5, 6]
    assert roadmap[0]['rfcs'] == ['RFC 7692', 'RFC 9110 §9.3.6', 'RFC 9110 §6.5', 'RFC 9110 §8', 'RFC 6960']
    assert roadmap[1]['rfcs'] == ['RFC 7232']
    assert roadmap[2]['rfcs'] == ['RFC 9530']

    competitors = data['competitor_matrix']['products']
    assert competitors['tigrcorn']['http3_quic'] == 'yes'
    assert competitors['tigrcorn']['connect_policy_surface'] == 'yes'
    assert competitors['uvicorn']['http1'] == 'documented_yes'
    assert competitors['uvicorn']['http2'] == 'no_official_support_claim_found'
    assert competitors['uvicorn']['websocket_permessage_deflate_policy'] == 'documented_yes'
    assert competitors['hypercorn']['http2'] == 'documented_yes'
    assert competitors['hypercorn']['http3_quic'] == 'documented_optional_yes'
    assert competitors['hypercorn']['quic_bind'] == 'documented_yes'
    assert competitors['daphne']['http2'] == 'documented_yes_with_tls_and_twisted_extras'
    assert competitors['daphne']['http3_quic'] == 'no_official_support_claim_found'
    assert competitors['granian']['http2'] == 'documented_yes'
    assert competitors['granian']['http3_quic'] == 'future_only_not_current'


def test_repository_documents_reference_rfc_applicability_report() -> None:
    root = Path(__file__).resolve().parents[1]
    report_name = 'RFC_APPLICABILITY_AND_COMPETITOR_STATUS.md'
    readme = (root / 'README.md').read_text(encoding='utf-8')
    current_state = (root / 'CURRENT_REPOSITORY_STATE.md').read_text(encoding='utf-8')
    conformance_readme = (root / 'docs' / 'review' / 'conformance' / 'README.md').read_text(encoding='utf-8')

    assert report_name in readme
    assert report_name in current_state
    assert report_name in conformance_readme
