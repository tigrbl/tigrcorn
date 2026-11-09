from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE_ROOT = ROOT / 'docs/review/conformance/releases/0.3.6/release-0.3.6'
FLOW_ROOT = RELEASE_ROOT / 'tigrcorn-minimum-certified-flow-control-matrix'

EXPECTED = {
    'http3-flow-control-aioquic-client-credit-exhaustion': 'http3-server-aioquic-client-post',
    'http3-flow-control-aioquic-client-replenishment': 'http3-server-aioquic-client-post',
    'http3-flow-control-aioquic-client-stream-backpressure': 'http3-server-aioquic-client-post',
    'http3-flow-control-aioquic-client-connection-backpressure': 'http3-server-aioquic-client-post',
    'http3-flow-control-aioquic-client-qpack-blocked-stream': 'http3-server-aioquic-client-post-goaway-qpack',
    'http3-flow-control-aioquic-client-goaway-pressure': 'http3-server-aioquic-client-post-goaway-qpack',
}


def test_bundle_index_registers_minimum_flow_bundle() -> None:
    payload = json.loads((RELEASE_ROOT / 'bundle_index.json').read_text(encoding='utf-8'))
    assert payload['bundles']['minimum_certified_flow_control'] == (
        'docs/review/conformance/releases/0.3.6/release-0.3.6/tigrcorn-minimum-certified-flow-control-matrix'
    )


def test_mapping_file_covers_all_phase5_flow_scenarios() -> None:
    payload = json.loads((FLOW_ROOT / 'scenario_mapping.json').read_text(encoding='utf-8'))
    got = {entry['id']: entry['source'] for entry in payload['mappings']}
    assert got == EXPECTED


def test_results_are_release_gate_eligible_and_traceable() -> None:
    for scenario_id, source in EXPECTED.items():
        result = json.loads((FLOW_ROOT / scenario_id / 'result.json').read_text(encoding='utf-8'))
        metadata = json.loads(
            (FLOW_ROOT / scenario_id / 'flow_control_metadata.json').read_text(
                encoding='utf-8'
            )
        )
        assert result['passed']
        assert result['release_gate_eligible']
        assert result['source_independent_scenario'] == source
        assert metadata['source_independent_scenario'] == source
        assert (FLOW_ROOT / scenario_id / 'packet_trace.jsonl').exists()
