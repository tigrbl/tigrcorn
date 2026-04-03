from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE_ROOT = ROOT / 'docs/review/conformance/releases/0.3.6/release-0.3.6'
PROVISIONAL_ROOT = RELEASE_ROOT / 'tigrcorn-provisional-flow-control-gap-bundle'
EXPECTED_SCENARIOS = {
    'http3-flow-control-public-client-post': 'http3-server-public-client-post',
    'http3-flow-control-public-client-post-retry': 'http3-server-public-client-post-retry',
    'http3-flow-control-public-client-post-zero-rtt': 'http3-server-public-client-post-zero-rtt',
    'http3-flow-control-public-client-post-migration': 'http3-server-public-client-post-migration',
    'http3-flow-control-public-client-post-goaway-qpack': 'http3-server-public-client-post-goaway-qpack',
}


def test_bundle_index_registers_relative_non_certifying_bundle() -> None:
    payload = json.loads((RELEASE_ROOT / 'bundle_index.json').read_text(encoding='utf-8'))
    provisional = payload['bundles']['provisional_flow_control_gap_bundle']
    assert provisional == (
        'docs/review/conformance/releases/0.3.6/release-0.3.6/tigrcorn-provisional-flow-control-gap-bundle'
    )
    assert 'flow-control gap bundle' in '\n'.join(payload['notes'])


def test_mapping_file_covers_all_flow_control_review_scenarios() -> None:
    mapping_payload = json.loads(
        (PROVISIONAL_ROOT / 'scenario_mapping.json').read_text(encoding='utf-8')
    )
    mappings = {
        entry['provisional_id']: entry['source_same_stack_id']
        for entry in mapping_payload['mappings']
    }
    assert mappings == EXPECTED_SCENARIOS


def test_each_provisional_result_is_explicitly_ineligible_for_release_gates() -> None:
    for scenario_id, source_id in EXPECTED_SCENARIOS.items():
        result = json.loads(
            (PROVISIONAL_ROOT / scenario_id / 'result.json').read_text(encoding='utf-8')
        )
        metadata = json.loads(
            (PROVISIONAL_ROOT / scenario_id / 'provisional_metadata.json').read_text(
                encoding='utf-8'
            )
        )
        vectors = json.loads(
            (PROVISIONAL_ROOT / scenario_id / 'source_local_vectors.json').read_text(
                encoding='utf-8'
            )
        )
        assert result['passed']
        assert result['provisional_non_certifying_substitution']
        assert result['flow_control_review_only']
        assert not result['release_gate_eligible']
        assert result['source_same_stack_scenario'] == source_id
        assert metadata['source_same_stack_scenario'] == source_id
        assert not metadata['release_gate_eligible']
        assert vectors
