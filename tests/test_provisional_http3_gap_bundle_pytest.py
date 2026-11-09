from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE_ROOT = ROOT / 'docs/review/conformance/releases/0.3.6/release-0.3.6'
PROVISIONAL_ROOT = RELEASE_ROOT / 'tigrcorn-provisional-http3-gap-bundle'
EXPECTED_SCENARIOS = {
    'http3-server-aioquic-client-post': 'http3-server-public-client-post',
    'http3-server-aioquic-client-post-mtls': 'http3-server-public-client-post-mtls',
    'http3-server-aioquic-client-post-retry': 'http3-server-public-client-post-retry',
    'http3-server-aioquic-client-post-resumption': 'http3-server-public-client-post-resumption',
    'http3-server-aioquic-client-post-zero-rtt': 'http3-server-public-client-post-zero-rtt',
    'http3-server-aioquic-client-post-migration': 'http3-server-public-client-post-migration',
    'http3-server-aioquic-client-post-goaway-qpack': 'http3-server-public-client-post-goaway-qpack',
    'websocket-http3-server-aioquic-client': 'websocket-http3-server-public-client',
    'websocket-http3-server-aioquic-client-mtls': 'websocket-http3-server-public-client-mtls',
}


def test_bundle_index_registers_relative_non_certifying_bundle() -> None:
    payload = json.loads((RELEASE_ROOT / 'bundle_index.json').read_text(encoding='utf-8'))
    provisional = payload['bundles']['provisional_http3_gap_bundle']
    assert provisional == (
        'docs/review/conformance/releases/0.3.6/release-0.3.6/tigrcorn-provisional-http3-gap-bundle'
    )
    assert 'explicitly non-certifying' in '\n'.join(payload['notes'])


def test_mapping_file_covers_all_missing_scenarios() -> None:
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
        assert result['passed']
        assert result['provisional_non_certifying_substitution']
        assert not result['release_gate_eligible']
        assert result['source_same_stack_scenario'] == source_id
        assert metadata['source_same_stack_scenario'] == source_id
        assert not metadata['release_gate_eligible']
        assert result['artifact_dir'].startswith(
            'docs/review/conformance/releases/0.3.6/release-0.3.6/'
        )
