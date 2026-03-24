from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFORMANCE = ROOT / 'docs' / 'review' / 'conformance'
PERFORMANCE = ROOT / 'docs' / 'review' / 'performance'


def _load_json(relative_path: str) -> dict:
    return json.loads((ROOT / relative_path).read_text(encoding='utf-8'))


def test_phase9a_contract_freeze_docs_and_release_root_exist() -> None:
    doc = CONFORMANCE / 'PHASE9A_PROMOTION_CONTRACT_FREEZE.md'
    backlog_doc = CONFORMANCE / 'PHASE9A_EXECUTION_BACKLOG.md'
    status_json = CONFORMANCE / 'phase9a_promotion_contract.current.json'
    backlog_json = CONFORMANCE / 'phase9a_execution_backlog.current.json'
    delivery = ROOT / 'DELIVERY_NOTES_PHASE9A_PROMOTION_CONTRACT_FREEZE.md'
    release_root = CONFORMANCE / 'releases' / '0.3.8' / 'release-0.3.8'
    manifest = release_root / 'manifest.json'
    readme = release_root / 'README.md'

    assert doc.exists()
    assert backlog_doc.exists()
    assert status_json.exists()
    assert backlog_json.exists()
    assert delivery.exists()
    assert release_root.exists()
    assert manifest.exists()
    assert readme.exists()

    text = doc.read_text(encoding='utf-8')
    assert 'Phase 9A' in text
    assert '0.3.8' in text
    assert '0.3.7' in text
    assert '13 strict-target independent-scenario gaps' in text
    assert '7 public flag/runtime gaps' in text
    assert 'not yet' in text and 'certifiably fully featured' in text


def test_phase9a_status_snapshot_freezes_release_root_policy_and_scope() -> None:
    payload = _load_json('docs/review/conformance/phase9a_promotion_contract.current.json')
    assert payload['phase'] == '9A'
    assert payload['checkpoint'] == 'phase9a_promotion_contract_freeze'
    assert payload['contract_frozen'] is True
    assert payload['status'] == 'contract_frozen_not_yet_strict_complete'

    current = payload['current_state']
    assert current['authoritative_boundary_passed'] is True
    assert current['strict_target_boundary_passed'] is False
    assert current['flag_surface_passed'] is False
    assert current['operator_surface_passed'] is True
    assert current['performance_passed'] is False
    assert current['documentation_passed'] is True
    assert current['final_promotion_gate_passed'] is False
    assert len(current['strict_target_missing_independent_scenarios']) == 13
    assert len(current['flag_runtime_blockers']) == 7

    policy = payload['release_root_policy']
    assert policy['immutable_candidate_release_root'].endswith('releases/0.3.7/release-0.3.7')
    assert policy['allow_mutation_of_candidate_release_root'] is False
    assert policy['next_promotable_release_root'].endswith('releases/0.3.8/release-0.3.8')
    assert policy['next_promotable_release_root_frozen'] is True

    operator = payload['operator_surface_no_regression']
    assert operator['must_remain_green'] is True
    assert set(operator['required_implemented_keys']) == {
        'workers_process_supervision',
        'reload',
        'proxy_header_normalization',
        'root_path_scope_injection',
        'structured_logging',
        'metrics_endpoint',
        'resource_timeout_controls_wired',
    }

    assert payload['out_of_scope_until_strict_target_green'] == [
        'RFC 7232',
        'RFC 9530',
        'RFC 9111',
        'RFC 9421',
        'JOSE',
        'COSE',
    ]


def test_phase9a_backlog_tracks_every_remaining_strict_scenario_and_flag_gap() -> None:
    payload = _load_json('docs/review/conformance/phase9a_execution_backlog.current.json')
    strict_rows = payload['strict_target_scenario_rows']
    flag_rows = payload['public_flag_closure_rows']

    assert len(strict_rows) == 13
    assert len(flag_rows) == 7

    strict_ids = {row['scenario_id'] for row in strict_rows}
    assert 'websocket-http11-server-websockets-client-permessage-deflate' in strict_ids
    assert 'http3-content-coding-aioquic-client' in strict_ids
    assert 'tls-server-ocsp-validation-openssl-client' in strict_ids

    for row in strict_rows:
        assert row['owner_role']
        assert row['target_phase'] in {'9C', '9D', '9E'}
        assert row['touch_files']
        assert row['artifact_contract']['required_scenario_files']
        assert row['exit_tests']

    flag_ids = {row['flag'] for row in flag_rows}
    assert flag_ids == {
        '--ssl-ciphers',
        '--log-config',
        '--statsd-host',
        '--otel-endpoint',
        '--limit-concurrency',
        '--websocket-ping-interval',
        '--websocket-ping-timeout',
    }

    for row in flag_rows:
        assert row['owner_role']
        assert row['target_phase'] == '9F'
        assert row['touch_files']
        assert row['artifact_contract']['required_state_transition']
        assert row['exit_tests']

    performance = payload['performance_closure_contract']
    assert performance['owner_role'] == 'performance_owner'
    assert 'docs/review/performance/performance_matrix.json' in performance['touch_files']
    assert 'p99_9_ms' in performance['artifact_contract']['required_metric_keys']
    assert 'max_p99_9_ms' in performance['artifact_contract']['required_threshold_keys']
    assert 'max_cpu_increase_fraction' in performance['artifact_contract']['required_relative_regression_budget_keys']
    assert 'end_to_end_release' in performance['artifact_contract']['required_matrix_lanes']

    gate = payload['gate_hardening_contract']
    assert gate['owner_role'] == 'promotion_gate_owner'
    assert 'required_artifact_files' in gate['artifact_contract']['must_enforce']
    assert 'missing_lane' in gate['artifact_contract']['required_negative_fixture_classes']


def test_phase9a_updates_contract_files_and_readmes() -> None:
    strict_text = (CONFORMANCE / 'STRICT_PROFILE_TARGET.md').read_text(encoding='utf-8')
    flag_text = (CONFORMANCE / 'FLAG_CERTIFICATION_TARGET.md').read_text(encoding='utf-8')
    perf_text = (PERFORMANCE / 'PERFORMANCE_SLOS.md').read_text(encoding='utf-8')
    current_state = (ROOT / 'CURRENT_REPOSITORY_STATE.md').read_text(encoding='utf-8')
    root_readme = (ROOT / 'README.md').read_text(encoding='utf-8')
    conf_readme = (CONFORMANCE / 'README.md').read_text(encoding='utf-8')
    plan_json = _load_json('docs/review/conformance/phase9_implementation_plan.current.json')
    contracts = _load_json('docs/review/conformance/flag_contracts.json')
    covering = _load_json('docs/review/conformance/flag_covering_array.json')
    promo = _load_json('docs/review/conformance/promotion_gate.target.json')

    assert 'PHASE9A_PROMOTION_CONTRACT_FREEZE.md' in strict_text
    assert 'phase9a_execution_backlog.current.json' in strict_text
    assert 'RFC 7232, RFC 9530, RFC 9111, RFC 9421, JOSE, and COSE remain out-of-scope' in strict_text

    assert 'PHASE9A_EXECUTION_BACKLOG.md' in flag_text
    assert 'phase9a_execution_backlog.current.json' in flag_text
    assert 'Row-level delivery metadata' in flag_text

    assert 'phase9a_promotion_contract.current.json' in perf_text
    assert 'fixed contract data' in perf_text

    assert '## Phase 9A promotion-contract-freeze checkpoint' in current_state
    assert 'phase9a_promotion_contract.current.json' in current_state
    assert 'phase9a_execution_backlog.current.json' in current_state

    assert 'PHASE9A_PROMOTION_CONTRACT_FREEZE.md' in root_readme
    assert 'phase9a_promotion_contract.current.json' in root_readme
    assert 'PHASE9A_PROMOTION_CONTRACT_FREEZE.md' in conf_readme
    assert 'phase9a_execution_backlog.current.json' in conf_readme

    assert plan_json['phase_execution_status']['9A']['status'] == 'completed'
    assert 'phase9a_contract_freeze' in contracts
    assert 'phase9a_contract_freeze' in covering
    assert 'phase9a_contract_freeze' in promo

    blocking = contracts['phase9a_contract_freeze']['blocking_flags']
    assert set(blocking) == {
        '--ssl-ciphers',
        '--log-config',
        '--statsd-host',
        '--otel-endpoint',
        '--limit-concurrency',
        '--websocket-ping-interval',
        '--websocket-ping-timeout',
    }

    rows = {row['flag_strings'][0]: row for row in contracts['contracts']}
    assert rows['--ssl-ciphers']['phase9a_delivery']['owner_role'] == 'tls_runtime_owner'
    assert rows['--log-config']['phase9a_delivery']['owner_role'] == 'observability_owner'
    assert rows['--limit-concurrency']['phase9a_delivery']['owner_role'] == 'scheduler_runtime_owner'
    assert rows['--websocket-ping-timeout']['phase9a_delivery']['owner_role'] == 'websocket_runtime_owner'
