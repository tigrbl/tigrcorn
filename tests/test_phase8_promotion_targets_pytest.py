from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from tigrcorn.cli import build_parser
from tigrcorn.compat.release_gates import evaluate_promotion_target

ROOT = Path(__file__).resolve().parents[1]
PROMOTION_REPORT = evaluate_promotion_target(ROOT)


def _load_json(relative_path: str) -> dict:
    return json.loads((ROOT / relative_path).read_text(encoding='utf-8'))


def test_strict_target_boundary_uses_current_boundary_schema_and_promotes_required_rfcs() -> None:
    authoritative = _load_json('docs/review/conformance/certification_boundary.json')
    strict_target = _load_json(
        'docs/review/conformance/certification_boundary.strict_target.json'
    )
    assert set(strict_target) == set(authoritative)
    assert strict_target['canonical_doc'] == 'docs/review/conformance/STRICT_PROFILE_TARGET.md'
    for rfc in [
        'RFC 7692',
        'RFC 9110 §9.3.6',
        'RFC 9110 §6.5',
        'RFC 9110 §8',
        'RFC 6960',
    ]:
        assert (
            authoritative['required_rfc_evidence'][rfc]['highest_required_evidence_tier']
            == 'local_conformance'
        )
        assert (
            strict_target['required_rfc_evidence'][rfc]['highest_required_evidence_tier']
            == 'independent_certification'
        )
        assert (
            'independent_certification'
            in strict_target['required_rfc_evidence'][rfc]['declared_evidence']
        )


def test_flag_contracts_cover_every_public_flag_and_record_current_gaps() -> None:
    parser = build_parser()
    public_flags: set[str] = set()
    for action in parser._actions:
        if isinstance(action, argparse._HelpAction):
            continue
        if action.help == argparse.SUPPRESS:
            continue
        for flag in action.option_strings:
            if flag.startswith('--'):
                public_flags.add(flag)

    payload = _load_json('docs/review/conformance/flag_contracts.json')
    contracts = payload['contracts']
    contract_flags = {row['flag_strings'][0] for row in contracts}
    assert payload['contract_mode'] == 'one_row_per_concrete_public_flag'
    assert payload['public_flag_string_count'] == len(public_flags)
    assert contract_flags == public_flags
    assert len(contracts) == len(public_flags)

    gaps = {
        row['flag_strings'][0]: row['status']['current_runtime_state']
        for row in contracts
        if row['flag_strings'][0]
        in {
            '--limit-concurrency',
            '--websocket-ping-interval',
            '--websocket-ping-timeout',
        }
    }
    assert gaps == {
        '--limit-concurrency': 'implemented',
        '--websocket-ping-interval': 'implemented',
        '--websocket-ping-timeout': 'implemented',
    }


def test_flag_covering_array_declares_required_hazard_clusters_and_full_one_way_coverage() -> None:
    payload = _load_json('docs/review/conformance/flag_covering_array.json')
    hazard_clusters = {entry['cluster_id'] for entry in payload['hazard_clusters']}
    assert hazard_clusters == {
        'transport_protocol_tls',
        'protocol_timeout_concurrency',
        'websocket_compression_carrier_transport',
        'semantic_extensions_by_http_version',
        'workers_reload_inherited_fd',
    }
    covered_flags: set[str] = set()
    for case in payload['cases']:
        for dimension in case['dimensions']:
            if 'flag' in dimension:
                covered_flags.add(dimension['flag'])
    contract_payload = _load_json('docs/review/conformance/flag_contracts.json')
    contract_flags = {row['flag_strings'][0] for row in contract_payload['contracts']}
    assert covered_flags == contract_flags
    assert payload['public_flag_string_count'] == len(contract_flags)


def test_performance_slo_target_declares_stricter_metric_threshold_and_budget_keys() -> None:
    slos = _load_json('docs/review/performance/performance_slos.json')
    assert 'component_regression' in slos['required_matrix_lanes']
    assert 'end_to_end_release' in slos['required_matrix_lanes']
    assert 'p99_9_ms' in slos['required_metric_keys']
    assert 'time_to_first_byte_ms' in slos['required_metric_keys']
    assert 'handshake_latency_ms' in slos['required_metric_keys']
    assert 'max_p99_9_ms' in slos['required_threshold_keys']
    assert 'max_time_to_first_byte_ms' in slos['required_threshold_keys']
    assert 'max_handshake_latency_ms' in slos['required_threshold_keys']
    assert 'max_p99_9_increase_fraction' in slos['required_relative_regression_budget_keys']
    assert 'max_cpu_increase_fraction' in slos['required_relative_regression_budget_keys']
    assert 'max_rss_increase_fraction' in slos['required_relative_regression_budget_keys']
    assert 'correctness.json' in slos['required_artifact_files']
    assert set(slos['required_matrix_lanes']) == {'component_regression', 'end_to_end_release'}
    assert slos['promotion_requirements']['require_correctness_under_load_for_rfc_targets']
    assert slos['promotion_requirements']['require_end_to_end_live_listener_profiles']
    assert slos['promotion_requirements']['require_certification_platforms']
    assert slos['promotion_requirements']['require_documented_slos_per_profile']


def test_composite_promotion_evaluator_reports_current_dual_boundary_state() -> None:
    report = PROMOTION_REPORT
    assert report.authoritative_boundary.passed, report.authoritative_boundary.failures
    assert report.strict_target_boundary.passed
    assert report.flag_surface.passed, report.flag_surface.failures
    assert report.operator_surface.passed
    assert report.performance.passed, report.performance.failures
    assert report.documentation.passed, report.documentation.failures
    assert report.passed

    strict_failures = '\n'.join(report.strict_target_boundary.failures)
    assert (
        'RFC 7692 independent_certification scenario websocket-http3-server-aioquic-client-permessage-deflate has preserved artifacts but they are not marked passing'
        not in strict_failures
    )
    assert (
        'RFC 7692 requires independent_certification evidence, but the resolved evidence only reaches local_conformance'
        not in strict_failures
    )
    assert (
        'RFC 9110 §9.3.6 independent_certification scenario http3-connect-relay-aioquic-client has preserved artifacts but they are not marked passing'
        not in strict_failures
    )
    assert (
        'RFC 9110 §9.3.6 references unknown independent_certification scenario http11-connect-relay-curl-client'
        not in strict_failures
    )
    assert (
        'RFC 9110 §6.5 independent_certification scenario http3-trailer-fields-aioquic-client has preserved artifacts but they are not marked passing'
        not in strict_failures
    )
    assert (
        'RFC 9110 §6.5 references unknown independent_certification scenario http11-trailer-fields-curl-client'
        not in strict_failures
    )
    assert strict_failures == ''
    assert (
        'RFC 9110 §8 references unknown independent_certification scenario http11-content-coding-curl-client'
        not in strict_failures
    )
    assert (
        'RFC 6960 references unknown independent_certification scenario tls-server-ocsp-validation-openssl-client'
        not in strict_failures
    )
    assert (
        'RFC 6960 requires independent_certification evidence, but the resolved evidence only reaches local_conformance'
        not in strict_failures
    )

    flag_failures = '\n'.join(report.flag_surface.failures)
    assert flag_failures == ''
    for flag in [
        '--ssl-ciphers',
        '--limit-concurrency',
        '--websocket-ping-interval',
        '--websocket-ping-timeout',
        '--log-config',
        '--otel-endpoint',
        '--statsd-host',
    ]:
        assert flag not in flag_failures

    perf_failures = '\n'.join(report.performance.failures)
    assert perf_failures == ''


def test_phase8_status_snapshot_matches_composite_report() -> None:
    snapshot = _load_json(
        'docs/review/conformance/phase8_strict_promotion_target_status.current.json'
    )
    assert snapshot['phase'] == 8
    assert snapshot['checkpoint'] == 'strict_promotion_targets_documented'
    assert snapshot['authoritative_boundary_passed'] == PROMOTION_REPORT.authoritative_boundary.passed
    assert snapshot['strict_target_boundary_passed'] == PROMOTION_REPORT.strict_target_boundary.passed
    assert snapshot['flag_surface_passed'] == PROMOTION_REPORT.flag_surface.passed
    assert snapshot['operator_surface_passed'] == PROMOTION_REPORT.operator_surface.passed
    assert snapshot['performance_passed'] == PROMOTION_REPORT.performance.passed
    assert snapshot['documentation_passed'] == PROMOTION_REPORT.documentation.passed
    assert snapshot['final_promotion_gate_passed'] == PROMOTION_REPORT.passed
    assert snapshot['blockers']['documentation'] == []


def test_phase8_status_tool_regenerates_snapshot_consistently() -> None:
    subprocess.run(
        [sys.executable, str(ROOT / 'tools' / 'create_phase8_promotion_target_status.py')],
        check=True,
        cwd=ROOT,
    )
    snapshot = json.loads(
        (
            ROOT
            / 'docs/review/conformance/phase8_strict_promotion_target_status.current.json'
        ).read_text(encoding='utf-8')
    )
    assert snapshot['phase'] == 8
    assert snapshot['checkpoint'] == 'strict_promotion_targets_documented'
    assert snapshot['authoritative_boundary_passed']
    assert snapshot['strict_target_boundary_passed']
    assert snapshot['flag_surface_passed']
    assert snapshot['operator_surface_passed']
    assert snapshot['performance_passed']
    assert snapshot['documentation_passed']
    assert snapshot['final_promotion_gate_passed']
