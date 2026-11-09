from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFORMANCE = ROOT / 'docs' / 'review' / 'conformance'


def test_release_certification_plan_documents_exist_and_remain_honest() -> None:
    plan_md = CONFORMANCE / 'RELEASE_IMPLEMENTATION_PLAN.md'
    plan_json = CONFORMANCE / 'release_implementation_plan.current.json'
    delivery = ROOT / 'docs/review/conformance/delivery/DELIVERY_NOTES_RELEASE_IMPLEMENTATION_PLAN.md'

    assert plan_md.exists(), 'expected release_certification implementation plan markdown to exist'
    assert plan_json.exists(), 'expected release_certification implementation plan json to exist'
    assert delivery.exists(), 'expected delivery notes for the plan checkpoint to exist'

    text = plan_md.read_text(encoding='utf-8')
    assert 'It is **not** a claim that the current tree is already strict-target complete.' in text
    assert 'strict target boundary: blocked by 10 still-missing independent third-party scenarios plus 1 preserved failing RFC 7692 HTTP/3 artifact' in text
    assert 'flag surface: blocked by 7 non-promotion-ready public flags' in text
    assert 'operator surface: green' in text
    assert 'performance target: blocked by stricter SLO and lane gaps' in text
    assert 'Do **not** mutate `docs/review/conformance/releases/0.3.7/release-0.3.7/`.' in text
    assert 'docs/review/conformance/releases/0.3.9/release-0.3.9/' in text


def test_release_certification_plan_json_tracks_current_blockers_and_exit_conditions() -> None:
    payload = json.loads((CONFORMANCE / 'release_implementation_plan.current.json').read_text(encoding='utf-8'))
    assert payload['phase'] == 9
    assert payload['checkpoint'] == 'release_implementation_plan_checkpoint'

    current = payload['current_state']
    assert current['authoritative_boundary_passed'] is True
    assert current['strict_target_boundary_passed'] is False
    assert current['flag_surface_passed'] is False
    assert current['operator_surface_passed'] is True
    assert current['performance_passed'] is False
    assert current['documentation_passed'] is True
    assert current['final_promotion_gate_passed'] is False

    assert len(current['strict_target_missing_independent_scenarios']) == 10
    assert len(current['flag_runtime_blockers']) == 7
    assert 'tls-server-ocsp-validation-openssl-client' in current['strict_target_missing_independent_scenarios']
    assert current['strict_target_non_passing_independent_scenarios'] == ['websocket-http3-server-aioquic-client-permessage-deflate']
    assert '--limit-concurrency' in current['flag_runtime_blockers']

    phases = {entry['phase_id']: entry for entry in payload['phases']}
    for phase_id in ['9A', '9B', '9C', '9D', '9E', '9F', '9G', '9H', '9I', '10']:
        assert phase_id in phases

    assert phases['9C']['blockers_closed'] == [
        'websocket-http11-server-websockets-client-permessage-deflate',
        'websocket-http2-server-h2-client-permessage-deflate',
        'websocket-http3-server-aioquic-client-permessage-deflate',
    ]
    assert 'src/tigrcorn/security/tls13/handshake.py' in phases['9F']['key_files']
    assert 'docs/review/performance/performance_matrix.json' in phases['9G']['key_files']
    assert 'src/tigrcorn/compat/release_gates.py' in phases['9H']['key_files']
    assert phases['9I']['dependencies'] == ['9C', '9D', '9E', '9F', '9G', '9H']

    definition = payload['promotion_definition_of_done']
    assert any('all 13 missing strict-target scenarios' in item for item in definition)
    assert payload['release_execution_status']['9B']['status'] == 'completed'
    assert payload['release_execution_status']['9C']['status'] == 'partially_completed'
    assert any('all 7 remaining public flag gaps' in item for item in definition)
    assert any('promotion evaluator enforces the full target contract' in item for item in definition)


def test_current_state_and_readmes_point_to_release_certification_plan() -> None:
    current_state = (ROOT / 'docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md').read_text(encoding='utf-8')
    conformance_readme = (CONFORMANCE / 'README.md').read_text(encoding='utf-8')
    top_readme = (ROOT / 'README.md').read_text(encoding='utf-8')

    assert '## Release certification implementation-plan checkpoint' in current_state
    assert 'RELEASE_IMPLEMENTATION_PLAN.md' in current_state
    assert 'release_implementation_plan.current.json' in current_state

    assert 'RELEASE_IMPLEMENTATION_PLAN.md' in conformance_readme
    assert 'release_implementation_plan.current.json' in conformance_readme
    assert 'RELEASE_IMPLEMENTATION_PLAN.md' in top_readme
    assert 'release_implementation_plan.current.json' in top_readme
