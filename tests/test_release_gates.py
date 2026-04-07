from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from tigrcorn.compat.release_gates import evaluate_promotion_target, evaluate_release_gates

ROOT = Path(__file__).resolve().parents[1]


class ReleaseGateTests(unittest.TestCase):
    def test_actual_repository_release_gates_pass_for_the_committed_tree(self):
        report = evaluate_release_gates(ROOT)
        self.assertTrue(report.passed, msg='\n'.join(report.failures))
        self.assertEqual(report.failures, [])
        self.assertEqual(report.rfc_status['RFC 9114']['highest_observed_evidence_tier'], 'independent_certification')
        self.assertEqual(report.rfc_status['RFC 9220']['highest_observed_evidence_tier'], 'independent_certification')
        self.assertEqual(report.rfc_status['RFC 9002']['highest_observed_evidence_tier'], 'independent_certification')

    def test_synthetic_release_tree_passes_when_boundary_evidence_and_artifacts_align(self):
        with tempfile.TemporaryDirectory(dir=os.getcwd()) as tmpdir:
            root = Path(tmpdir)
            (root / 'docs/review/conformance').mkdir(parents=True)
            (root / 'src/tigrcorn/security').mkdir(parents=True)
            for relative in [
                'README.md',
                'docs/protocols/http3.md',
                'docs/protocols/quic.md',
                'docs/protocols/websocket.md',
                'docs/review/conformance/README.md',
                'docs/review/rfc_compliance_review.md',
                'docs/review/conformance/reports/RFC_HARDENING_REPORT.md',
                'docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md',
                'docs/review/conformance/reports/RFC_CERTIFICATION_STATUS.md',
            ]:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('See docs/review/conformance/CERTIFICATION_BOUNDARY.md\n', encoding='utf-8')
            (root / 'docs/review/conformance/CERTIFICATION_BOUNDARY.md').write_text('# boundary\n', encoding='utf-8')
            (root / 'src/tigrcorn/security/tls.py').write_text('def build_server_tls_context():\n    return None\n', encoding='utf-8')
            corpus = {
                'vectors': [
                    {'name': 'http3-server-surface', 'protocol': 'http3', 'rfc': '9114', 'description': 'local http3', 'fixture': 'tests/test_http3_rfc9114.py'},
                    {'name': 'http3-websocket-extended-connect', 'protocol': 'http3-websocket', 'rfc': '9220', 'description': 'local h3 websocket', 'fixture': 'tests/test_http3_websocket_rfc9220.py'},
                ]
            }
            (root / 'docs/review/conformance/corpus.json').write_text(json.dumps(corpus), encoding='utf-8')
            independent_matrix = {
                'name': 'independent',
                'metadata': {'evidence_tier': 'independent_certification'},
                'scenarios': [
                    {
                        'id': 'http3-third-party-post',
                        'protocol': 'http3',
                        'role': 'server',
                        'feature': 'post-echo',
                        'peer': 'aioquic',
                        'enabled': True,
                        'evidence_tier': 'independent_certification',
                        'metadata': {'rfc': ['RFC 9114']},
                        'sut': {
                            'name': 'tigrcorn-http3',
                            'adapter': 'subprocess',
                            'role': 'server',
                            'command': ['python', '-m', 'tigrcorn'],
                            'provenance_kind': 'package_owned',
                            'implementation_source': 'tigrcorn',
                            'implementation_identity': 'tigrcorn-http3',
                        },
                        'peer_process': {
                            'name': 'aioquic-http3-client',
                            'adapter': 'subprocess',
                            'role': 'client',
                            'command': ['python', '-m', 'example.h3client'],
                            'provenance_kind': 'third_party_library',
                            'implementation_source': 'aioquic',
                            'implementation_identity': 'aioquic-http3-client',
                        },
                    },
                    {
                        'id': 'http3-third-party-websocket',
                        'protocol': 'http3',
                        'role': 'server',
                        'feature': 'websocket-echo',
                        'peer': 'aioquic',
                        'enabled': True,
                        'evidence_tier': 'independent_certification',
                        'metadata': {'rfc': ['RFC 9220']},
                        'sut': {
                            'name': 'tigrcorn-http3',
                            'adapter': 'subprocess',
                            'role': 'server',
                            'command': ['python', '-m', 'tigrcorn'],
                            'provenance_kind': 'package_owned',
                            'implementation_source': 'tigrcorn',
                            'implementation_identity': 'tigrcorn-http3',
                        },
                        'peer_process': {
                            'name': 'aioquic-http3-websocket-client',
                            'adapter': 'subprocess',
                            'role': 'client',
                            'command': ['python', '-m', 'example.h3wsclient'],
                            'provenance_kind': 'third_party_library',
                            'implementation_source': 'aioquic',
                            'implementation_identity': 'aioquic-http3-websocket-client',
                        },
                    },
                ],
            }
            same_stack_matrix = {
                'name': 'same-stack',
                'metadata': {'evidence_tier': 'same_stack_replay'},
                'scenarios': [
                    {
                        'id': 'same-stack-http3',
                        'protocol': 'http3',
                        'role': 'server',
                        'feature': 'post-echo',
                        'peer': 'tigrcorn-public-client',
                        'enabled': True,
                        'evidence_tier': 'same_stack_replay',
                        'metadata': {'rfc': ['RFC 9114']},
                        'sut': {
                            'name': 'tigrcorn-http3',
                            'adapter': 'subprocess',
                            'role': 'server',
                            'command': ['python', '-m', 'tigrcorn'],
                            'provenance_kind': 'package_owned',
                            'implementation_source': 'tigrcorn',
                            'implementation_identity': 'tigrcorn-http3',
                        },
                        'peer_process': {
                            'name': 'tigrcorn-public-client',
                            'adapter': 'subprocess',
                            'role': 'client',
                            'command': ['python', '-m', 'tests.fixtures_pkg.external_http3_client'],
                            'provenance_kind': 'same_stack_fixture',
                            'implementation_source': 'tigrcorn.tests.fixtures_pkg',
                            'implementation_identity': 'tigrcorn-public-client',
                        },
                    }
                ],
            }
            (root / 'docs/review/conformance/external_matrix.release.json').write_text(json.dumps(independent_matrix), encoding='utf-8')
            (root / 'docs/review/conformance/external_matrix.same_stack_replay.json').write_text(json.dumps(same_stack_matrix), encoding='utf-8')

            independent_root = root / 'docs/review/conformance/releases/current/independent'
            independent_root.mkdir(parents=True)
            for scenario_id in ['http3-third-party-post', 'http3-third-party-websocket']:
                scenario_root = independent_root / scenario_id
                scenario_root.mkdir(parents=True)
                (scenario_root / 'result.json').write_text(json.dumps({'passed': True}), encoding='utf-8')
            (independent_root / 'index.json').write_text(
                json.dumps(
                    {
                        'scenarios': [
                            {'id': 'http3-third-party-post', 'passed': True},
                            {'id': 'http3-third-party-websocket', 'passed': True},
                        ]
                    }
                ),
                encoding='utf-8',
            )
            (independent_root / 'manifest.json').write_text(json.dumps({'bundle_kind': 'independent_certification'}), encoding='utf-8')

            same_stack_root = root / 'docs/review/conformance/releases/current/same-stack'
            same_stack_root.mkdir(parents=True)
            scenario_root = same_stack_root / 'same-stack-http3'
            scenario_root.mkdir(parents=True)
            (scenario_root / 'result.json').write_text(json.dumps({'passed': True}), encoding='utf-8')
            (same_stack_root / 'index.json').write_text(json.dumps({'scenarios': [{'id': 'same-stack-http3', 'passed': True}]}), encoding='utf-8')
            (same_stack_root / 'manifest.json').write_text(json.dumps({'bundle_kind': 'same_stack_replay'}), encoding='utf-8')

            boundary = {
                'canonical_doc': 'docs/review/conformance/CERTIFICATION_BOUNDARY.md',
                'artifact_bundles': {
                    'independent_certification': 'docs/review/conformance/releases/current/independent',
                    'same_stack_replay': 'docs/review/conformance/releases/current/same-stack',
                },
                'required_rfcs': ['RFC 9114', 'RFC 9220'],
                'required_rfc_evidence': {
                    'RFC 9114': {
                        'highest_required_evidence_tier': 'independent_certification',
                        'declared_evidence': {
                            'local_conformance': ['http3-server-surface'],
                            'independent_certification': ['http3-third-party-post'],
                        },
                    },
                    'RFC 9220': {
                        'highest_required_evidence_tier': 'independent_certification',
                        'declared_evidence': {
                            'local_conformance': ['http3-websocket-extended-connect'],
                            'independent_certification': ['http3-third-party-websocket'],
                        },
                    },
                },
                'gates': {
                    'require_independent_matrix': True,
                    'require_third_party_http3_request_response': True,
                    'require_third_party_http3_websocket': True,
                    'require_package_owned_tls13_subsystem': True,
                    'require_docs_reference_canonical_boundary': True,
                    'require_conformance_corpus': True,
                    'require_rfc_evidence_map': True,
                    'require_preserved_artifacts_for_independent_scenarios': True,
                },
                'docs_that_must_reference_boundary': [
                    'README.md',
                    'docs/protocols/http3.md',
                    'docs/protocols/quic.md',
                    'docs/protocols/websocket.md',
                    'docs/review/conformance/README.md',
                    'docs/review/rfc_compliance_review.md',
                    'docs/review/conformance/reports/RFC_HARDENING_REPORT.md',
                    'docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md',
                    'docs/review/conformance/reports/RFC_CERTIFICATION_STATUS.md',
                ],
            }
            (root / 'docs/review/conformance/certification_boundary.json').write_text(json.dumps(boundary), encoding='utf-8')
            report = evaluate_release_gates(root)
            self.assertTrue(report.passed, msg=report.failures)


    def test_actual_repository_promotion_evaluator_keeps_performance_and_docs_green(self):
        report = evaluate_promotion_target(ROOT)
        self.assertTrue(report.performance.passed, msg='\n'.join(report.performance.failures))
        self.assertTrue(report.documentation.passed, msg='\n'.join(report.documentation.failures))
        self.assertTrue(report.passed)

    def test_release_gates_fail_closed_when_independent_matrix_declares_pending_scenarios(self):
        with tempfile.TemporaryDirectory(dir=os.getcwd()) as tmpdir:
            root = Path(tmpdir)
            (root / 'docs/review/conformance').mkdir(parents=True)
            (root / 'docs/review/conformance/releases/current/independent').mkdir(parents=True)
            (root / 'docs/review/conformance/releases/current/same-stack').mkdir(parents=True)
            (root / 'src/tigrcorn/security').mkdir(parents=True)
            for relative in [
                'README.md',
                'docs/protocols/http3.md',
                'docs/protocols/quic.md',
                'docs/protocols/websocket.md',
                'docs/review/conformance/README.md',
                'docs/review/rfc_compliance_review.md',
                'docs/review/conformance/reports/RFC_HARDENING_REPORT.md',
                'docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md',
                'docs/review/conformance/reports/RFC_CERTIFICATION_STATUS.md',
            ]:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('See docs/review/conformance/CERTIFICATION_BOUNDARY.md\n', encoding='utf-8')
            (root / 'docs/review/conformance/CERTIFICATION_BOUNDARY.md').write_text('# boundary\n', encoding='utf-8')
            (root / 'src/tigrcorn/security/tls.py').write_text('def build_server_tls_context():\n    return None\n', encoding='utf-8')
            (root / 'docs/review/conformance/corpus.json').write_text(json.dumps({'vectors': []}), encoding='utf-8')
            (root / 'docs/review/conformance/releases/current/independent/index.json').write_text(json.dumps({'scenarios': []}), encoding='utf-8')
            (root / 'docs/review/conformance/releases/current/independent/manifest.json').write_text(json.dumps({}), encoding='utf-8')
            (root / 'docs/review/conformance/releases/current/same-stack/index.json').write_text(json.dumps({'scenarios': []}), encoding='utf-8')
            (root / 'docs/review/conformance/releases/current/same-stack/manifest.json').write_text(json.dumps({}), encoding='utf-8')
            (root / 'docs/review/conformance/external_matrix.same_stack_replay.json').write_text(
                json.dumps({'name': 'same-stack', 'metadata': {'evidence_tier': 'same_stack_replay'}, 'scenarios': []}),
                encoding='utf-8',
            )
            (root / 'docs/review/conformance/external_matrix.release.json').write_text(
                json.dumps(
                    {
                        'name': 'independent',
                        'metadata': {
                            'evidence_tier': 'independent_certification',
                            'pending_third_party_http3_scenarios': ['http3-pending'],
                        },
                        'scenarios': [],
                    }
                ),
                encoding='utf-8',
            )
            boundary = {
                'canonical_doc': 'docs/review/conformance/CERTIFICATION_BOUNDARY.md',
                'artifact_bundles': {
                    'independent_certification': 'docs/review/conformance/releases/current/independent',
                    'same_stack_replay': 'docs/review/conformance/releases/current/same-stack',
                },
                'required_rfcs': [],
                'required_rfc_evidence': {},
                'gates': {
                    'require_independent_matrix': True,
                    'require_docs_reference_canonical_boundary': True,
                    'require_conformance_corpus': True,
                },
                'docs_that_must_reference_boundary': [
                    'README.md',
                    'docs/protocols/http3.md',
                    'docs/protocols/quic.md',
                    'docs/protocols/websocket.md',
                    'docs/review/conformance/README.md',
                    'docs/review/rfc_compliance_review.md',
                    'docs/review/conformance/reports/RFC_HARDENING_REPORT.md',
                    'docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md',
                    'docs/review/conformance/reports/RFC_CERTIFICATION_STATUS.md',
                ],
            }
            (root / 'docs/review/conformance/certification_boundary.json').write_text(json.dumps(boundary), encoding='utf-8')
            report = evaluate_release_gates(root)
            self.assertFalse(report.passed)
            self.assertIn('pending_third_party_http3_scenarios', '\n'.join(report.failures))

if __name__ == '__main__':
    unittest.main()
