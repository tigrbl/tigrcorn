from __future__ import annotations

import argparse
import json
import subprocess
import sys
import unittest
from pathlib import Path

from tigrcorn.cli import build_parser
from tigrcorn.compat.release_gates import evaluate_promotion_target

ROOT = Path(__file__).resolve().parents[1]
CONFORMANCE = ROOT / 'docs' / 'review' / 'conformance'
PERFORMANCE = ROOT / 'docs' / 'review' / 'performance'
PROMOTION_REPORT = evaluate_promotion_target(ROOT)


class Phase8PromotionTargetTests(unittest.TestCase):
    def _load_json(self, relative_path: str) -> dict:
        return json.loads((ROOT / relative_path).read_text(encoding='utf-8'))

    def test_strict_target_boundary_uses_current_boundary_schema_and_promotes_required_rfcs(self) -> None:
        authoritative = self._load_json('docs/review/conformance/certification_boundary.json')
        strict_target = self._load_json('docs/review/conformance/certification_boundary.strict_target.json')
        self.assertEqual(set(strict_target), set(authoritative))
        self.assertEqual(strict_target['canonical_doc'], 'docs/review/conformance/STRICT_PROFILE_TARGET.md')
        for rfc in ['RFC 7692', 'RFC 9110 §9.3.6', 'RFC 9110 §6.5', 'RFC 9110 §8', 'RFC 6960']:
            self.assertEqual(authoritative['required_rfc_evidence'][rfc]['highest_required_evidence_tier'], 'local_conformance')
            self.assertEqual(strict_target['required_rfc_evidence'][rfc]['highest_required_evidence_tier'], 'independent_certification')
            self.assertIn('independent_certification', strict_target['required_rfc_evidence'][rfc]['declared_evidence'])

    def test_flag_contracts_cover_every_public_flag_and_record_current_gaps(self) -> None:
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

        payload = self._load_json('docs/review/conformance/flag_contracts.json')
        contracts = payload['contracts']
        contract_flags = {row['flag_strings'][0] for row in contracts}
        self.assertEqual(payload['contract_mode'], 'one_row_per_concrete_public_flag')
        self.assertEqual(payload['public_flag_string_count'], len(public_flags))
        self.assertEqual(contract_flags, public_flags)
        self.assertEqual(len(contracts), len(public_flags))

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
        self.assertEqual(
            gaps,
            {
                '--limit-concurrency': 'implemented',
                '--websocket-ping-interval': 'implemented',
                '--websocket-ping-timeout': 'implemented',
            },
        )

    def test_flag_covering_array_declares_required_hazard_clusters_and_full_one_way_coverage(self) -> None:
        payload = self._load_json('docs/review/conformance/flag_covering_array.json')
        hazard_clusters = {entry['cluster_id'] for entry in payload['hazard_clusters']}
        self.assertEqual(
            hazard_clusters,
            {
                'transport_protocol_tls',
                'protocol_timeout_concurrency',
                'websocket_compression_carrier_transport',
                'semantic_extensions_by_http_version',
                'workers_reload_inherited_fd',
            },
        )
        covered_flags: set[str] = set()
        for case in payload['cases']:
            for dimension in case['dimensions']:
                if 'flag' in dimension:
                    covered_flags.add(dimension['flag'])
        contract_payload = self._load_json('docs/review/conformance/flag_contracts.json')
        contract_flags = {row['flag_strings'][0] for row in contract_payload['contracts']}
        self.assertEqual(covered_flags, contract_flags)
        self.assertEqual(payload['public_flag_string_count'], len(contract_flags))

    def test_performance_slo_target_declares_stricter_metric_threshold_and_budget_keys(self) -> None:
        slos = self._load_json('docs/review/performance/performance_slos.json')
        self.assertIn('component_regression', slos['required_matrix_lanes'])
        self.assertIn('end_to_end_release', slos['required_matrix_lanes'])
        self.assertIn('p99_9_ms', slos['required_metric_keys'])
        self.assertIn('time_to_first_byte_ms', slos['required_metric_keys'])
        self.assertIn('handshake_latency_ms', slos['required_metric_keys'])
        self.assertIn('max_p99_9_ms', slos['required_threshold_keys'])
        self.assertIn('max_time_to_first_byte_ms', slos['required_threshold_keys'])
        self.assertIn('max_handshake_latency_ms', slos['required_threshold_keys'])
        self.assertIn('max_p99_9_increase_fraction', slos['required_relative_regression_budget_keys'])
        self.assertIn('max_cpu_increase_fraction', slos['required_relative_regression_budget_keys'])
        self.assertIn('max_rss_increase_fraction', slos['required_relative_regression_budget_keys'])
        self.assertIn('correctness.json', slos['required_artifact_files'])
        self.assertEqual(set(slos['required_matrix_lanes']), {'component_regression', 'end_to_end_release'})
        self.assertTrue(slos['promotion_requirements']['require_correctness_under_load_for_rfc_targets'])
        self.assertTrue(slos['promotion_requirements']['require_end_to_end_live_listener_profiles'])
        self.assertTrue(slos['promotion_requirements']['require_certification_platforms'])
        self.assertTrue(slos['promotion_requirements']['require_documented_slos_per_profile'])

    def test_composite_promotion_evaluator_reports_current_dual_boundary_state(self) -> None:
        report = PROMOTION_REPORT
        self.assertTrue(report.authoritative_boundary.passed, msg=report.authoritative_boundary.failures)
        self.assertTrue(report.strict_target_boundary.passed)
        self.assertTrue(report.flag_surface.passed, msg=report.flag_surface.failures)
        self.assertTrue(report.operator_surface.passed)
        self.assertTrue(report.performance.passed, msg=report.performance.failures)
        self.assertTrue(report.documentation.passed, msg=report.documentation.failures)
        self.assertTrue(report.passed)
        self.assertTrue(report.strict_target_boundary.passed)

        strict_failures = '\n'.join(report.strict_target_boundary.failures)
        self.assertNotIn('RFC 7692 independent_certification scenario websocket-http3-server-aioquic-client-permessage-deflate has preserved artifacts but they are not marked passing', strict_failures)
        self.assertNotIn('RFC 7692 requires independent_certification evidence, but the resolved evidence only reaches local_conformance', strict_failures)
        self.assertNotIn('RFC 9110 §9.3.6 independent_certification scenario http3-connect-relay-aioquic-client has preserved artifacts but they are not marked passing', strict_failures)
        self.assertNotIn('RFC 9110 §9.3.6 references unknown independent_certification scenario http11-connect-relay-curl-client', strict_failures)
        self.assertNotIn('RFC 9110 §6.5 independent_certification scenario http3-trailer-fields-aioquic-client has preserved artifacts but they are not marked passing', strict_failures)
        self.assertNotIn('RFC 9110 §6.5 references unknown independent_certification scenario http11-trailer-fields-curl-client', strict_failures)
        self.assertEqual(strict_failures, '')
        self.assertNotIn('RFC 9110 §8 references unknown independent_certification scenario http11-content-coding-curl-client', strict_failures)
        self.assertNotIn('RFC 6960 references unknown independent_certification scenario tls-server-ocsp-validation-openssl-client', strict_failures)
        self.assertNotIn('RFC 6960 requires independent_certification evidence, but the resolved evidence only reaches local_conformance', strict_failures)

        flag_failures = '\n'.join(report.flag_surface.failures)
        self.assertEqual(flag_failures, '')
        for flag in [
            '--ssl-ciphers',
            '--limit-concurrency',
            '--websocket-ping-interval',
            '--websocket-ping-timeout',
            '--log-config',
            '--otel-endpoint',
            '--statsd-host',
        ]:
            self.assertNotIn(flag, flag_failures)

        perf_failures = '\n'.join(report.performance.failures)
        self.assertEqual(perf_failures, '')


    def test_phase8_status_snapshot_matches_composite_report(self) -> None:
        snapshot = self._load_json('docs/review/conformance/phase8_strict_promotion_target_status.current.json')
        self.assertEqual(snapshot['phase'], 8)
        self.assertEqual(snapshot['checkpoint'], 'strict_promotion_targets_documented')
        self.assertEqual(snapshot['authoritative_boundary_passed'], PROMOTION_REPORT.authoritative_boundary.passed)
        self.assertEqual(snapshot['strict_target_boundary_passed'], PROMOTION_REPORT.strict_target_boundary.passed)
        self.assertEqual(snapshot['flag_surface_passed'], PROMOTION_REPORT.flag_surface.passed)
        self.assertEqual(snapshot['operator_surface_passed'], PROMOTION_REPORT.operator_surface.passed)
        self.assertEqual(snapshot['performance_passed'], PROMOTION_REPORT.performance.passed)
        self.assertEqual(snapshot['documentation_passed'], PROMOTION_REPORT.documentation.passed)
        self.assertEqual(snapshot['final_promotion_gate_passed'], PROMOTION_REPORT.passed)
        self.assertEqual(snapshot['blockers']['documentation'], [])

    def test_phase8_status_tool_regenerates_snapshot_consistently(self) -> None:
        subprocess.run([sys.executable, str(ROOT / 'tools' / 'create_phase8_promotion_target_status.py')], check=True, cwd=ROOT)
        snapshot = json.loads((ROOT / 'docs/review/conformance/phase8_strict_promotion_target_status.current.json').read_text(encoding='utf-8'))
        self.assertEqual(snapshot['phase'], 8)
        self.assertEqual(snapshot['checkpoint'], 'strict_promotion_targets_documented')
        self.assertTrue(snapshot['authoritative_boundary_passed'])
        self.assertTrue(snapshot['strict_target_boundary_passed'])
        self.assertTrue(snapshot['flag_surface_passed'])
        self.assertTrue(snapshot['operator_surface_passed'])
        self.assertTrue(snapshot['performance_passed'])
        self.assertTrue(snapshot['documentation_passed'])
        self.assertTrue(snapshot['final_promotion_gate_passed'])


if __name__ == '__main__':
    unittest.main()
