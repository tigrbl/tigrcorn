from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from tigrcorn.compat.interop_runner import (
    ExternalInteropRunner,
    build_environment_manifest,
    load_external_matrix,
    summarize_matrix_dimensions,
)

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


class ExternalInteropRunnerTests(unittest.TestCase):
    def _write_matrix(self, payload: dict) -> Path:
        tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        path = Path(tmpdir.name) / 'matrix.json'
        path.write_text(json.dumps(payload), encoding='utf-8')
        return path

    def test_load_matrix_and_dimension_summary(self):
        matrix_path = self._write_matrix(
            {
                'name': 'dimension-check',
                'scenarios': [
                    {
                        'id': 'http1-ipv4',
                        'protocol': 'http1',
                        'role': 'server',
                        'feature': 'basic-get',
                        'peer': 'fixture-http-client',
                        'ip_family': 'ipv4',
                        'cipher_group': 'tls13-aes128',
                        'sut': {
                            'name': 'tigrcorn-http1',
                            'adapter': 'subprocess',
                            'role': 'server',
                            'command': [PYTHON, '-m', 'tigrcorn', 'examples.echo_http.app:app', '--host', '{bind_host}', '--port', '{bind_port}', '--protocol', 'http1', '--disable-websocket', '--no-access-log', '--lifespan', 'off'],
                            'ready_pattern': 'listening on',
                            'version_command': [PYTHON, '-m', 'tigrcorn', '--help'],
                        },
                        'peer_process': {
                            'name': 'fixture-http-client',
                            'adapter': 'subprocess',
                            'role': 'client',
                            'command': [PYTHON, '-m', 'tests.fixtures_pkg.interop_http_client'],
                            'version_command': [PYTHON, '-m', 'tests.fixtures_pkg.interop_http_client', '--version'],
                        },
                    },
                    {
                        'id': 'quic-ipv6',
                        'protocol': 'quic',
                        'role': 'client',
                        'feature': 'observer-qlog',
                        'peer': 'fixture-udp-echo',
                        'transport': 'udp',
                        'ip_family': 'ipv6',
                        'cipher_group': 'x25519-aes128',
                        'retry': True,
                        'resumption': True,
                        'zero_rtt': True,
                        'key_update': True,
                        'migration': True,
                        'goaway': True,
                        'qpack_blocking': True,
                        'sut': {
                            'name': 'fixture-quic-client',
                            'adapter': 'subprocess',
                            'role': 'client',
                            'command': [PYTHON, '-m', 'tests.fixtures_pkg.interop_quic_client'],
                            'version_command': [PYTHON, '-m', 'tests.fixtures_pkg.interop_quic_client', '--version'],
                        },
                        'peer_process': {
                            'name': 'fixture-udp-echo',
                            'adapter': 'subprocess',
                            'role': 'server',
                            'command': [PYTHON, '-m', 'tests.fixtures_pkg.interop_udp_echo_server'],
                            'ready_pattern': 'READY',
                            'version_command': [PYTHON, '-m', 'tests.fixtures_pkg.interop_udp_echo_server', '--version'],
                        },
                    },
                ],
            }
        )
        matrix = load_external_matrix(matrix_path)
        dimensions = summarize_matrix_dimensions(matrix)
        self.assertEqual(matrix.name, 'dimension-check')
        self.assertEqual(dimensions['protocol'], ['http1', 'quic'])
        self.assertEqual(dimensions['role'], ['client', 'server'])
        self.assertEqual(dimensions['ip_family'], ['ipv4', 'ipv6'])
        self.assertEqual(dimensions['retry'], [False, True])
        self.assertEqual(dimensions['qpack_blocking'], [False, True])

        self.assertEqual(dimensions['evidence_tier'], ['mixed'])

    def test_load_matrix_rejects_same_stack_peer_for_independent_certification(self):
        matrix_path = self._write_matrix(
            {
                'name': 'bad-independent-matrix',
                'metadata': {'evidence_tier': 'independent_certification'},
                'scenarios': [
                    {
                        'id': 'bad-http3',
                        'protocol': 'http3',
                        'role': 'server',
                        'feature': 'post-echo',
                        'peer': 'tigrcorn-public-client',
                        'evidence_tier': 'independent_certification',
                        'sut': {
                            'name': 'tigrcorn-http3',
                            'adapter': 'subprocess',
                            'role': 'server',
                            'command': [PYTHON, '-m', 'tigrcorn', 'examples.echo_http.app:app'],
                            'provenance_kind': 'package_owned',
                            'implementation_source': 'tigrcorn',
                            'implementation_identity': 'tigrcorn-http3',
                        },
                        'peer_process': {
                            'name': 'tigrcorn-public-client',
                            'adapter': 'subprocess',
                            'role': 'client',
                            'command': [PYTHON, '-m', 'tests.fixtures_pkg.external_http3_client'],
                            'provenance_kind': 'same_stack_fixture',
                            'implementation_source': 'tigrcorn.tests.fixtures_pkg',
                            'implementation_identity': 'tigrcorn-public-client',
                        },
                    }
                ],
            }
        )
        with self.assertRaisesRegex(RuntimeError, 'requires a third-party peer'):
            load_external_matrix(matrix_path)

    def test_runner_generates_http_evidence_bundle(self):
        matrix_path = self._write_matrix(
            {
                'name': 'http-evidence',
                'scenarios': [
                    {
                        'id': 'http1-server-fixture-client',
                        'protocol': 'http1',
                        'role': 'server',
                        'feature': 'post-echo',
                        'peer': 'fixture-http-client',
                        'sut': {
                            'name': 'tigrcorn-http1',
                            'adapter': 'subprocess',
                            'role': 'server',
                            'command': [PYTHON, '-m', 'tigrcorn', 'examples.echo_http.app:app', '--host', '{bind_host}', '--port', '{bind_port}', '--protocol', 'http1', '--disable-websocket', '--no-access-log', '--lifespan', 'off'],
                            'ready_pattern': 'listening on',
                            'version_command': [PYTHON, '-m', 'tigrcorn', '--help'],
                        },
                        'peer_process': {
                            'name': 'fixture-http-client',
                            'adapter': 'subprocess',
                            'role': 'client',
                            'command': [PYTHON, '-m', 'tests.fixtures_pkg.interop_http_client'],
                            'version_command': [PYTHON, '-m', 'tests.fixtures_pkg.interop_http_client', '--version'],
                        },
                        'assertions': [
                            {'path': 'peer.exit_code', 'equals': 0},
                            {'path': 'transcript.peer.response.status', 'equals': 200},
                            {'path': 'transcript.peer.response.body', 'equals': 'echo:hello-interop'},
                            {'path': 'artifacts.packet_trace.exists', 'equals': True},
                            {'path': 'artifacts.packet_trace.size', 'greater_or_equal': 1},
                            {'path': 'artifacts.peer_transcript.exists', 'equals': True},
                        ],
                    }
                ],
            }
        )
        with tempfile.TemporaryDirectory() as artifact_root:
            prior = os.environ.get('TIGRCORN_COMMIT_HASH')
            os.environ['TIGRCORN_COMMIT_HASH'] = 'deadbeefcafebabe'
            try:
                runner = ExternalInteropRunner(matrix=load_external_matrix(matrix_path), artifact_root=artifact_root, source_root=ROOT)
                summary = runner.run()
                self.assertEqual(summary.total, 1)
                self.assertEqual(summary.passed, 1)
                result = summary.scenarios[0]
                self.assertTrue(result.passed)
                self.assertEqual(result.transcript['peer']['response']['body'], 'echo:hello-interop')
                self.assertEqual(result.sut['provenance']['kind'], 'unspecified')
                self.assertEqual(result.peer['provenance']['kind'], 'unspecified')
                manifest = json.loads((Path(summary.artifact_root) / 'manifest.json').read_text(encoding='utf-8'))
                self.assertEqual(manifest['commit_hash'], 'deadbeefcafebabe')
                self.assertTrue((Path(result.artifact_dir) / 'packet_trace.jsonl').exists())
            finally:
                if prior is None:
                    os.environ.pop('TIGRCORN_COMMIT_HASH', None)
                else:
                    os.environ['TIGRCORN_COMMIT_HASH'] = prior

    def test_runner_generates_quic_qlog_bundle(self):
        matrix_path = self._write_matrix(
            {
                'name': 'quic-observer',
                'scenarios': [
                    {
                        'id': 'quic-client-fixture-server',
                        'protocol': 'quic',
                        'transport': 'udp',
                        'role': 'client',
                        'feature': 'initial-observer-qlog',
                        'peer': 'fixture-udp-echo',
                        'sut': {
                            'name': 'fixture-quic-client',
                            'adapter': 'subprocess',
                            'role': 'client',
                            'command': [PYTHON, '-m', 'tests.fixtures_pkg.interop_quic_client'],
                            'version_command': [PYTHON, '-m', 'tests.fixtures_pkg.interop_quic_client', '--version'],
                        },
                        'peer_process': {
                            'name': 'fixture-udp-echo',
                            'adapter': 'subprocess',
                            'role': 'server',
                            'command': [PYTHON, '-m', 'tests.fixtures_pkg.interop_udp_echo_server'],
                            'ready_pattern': 'READY',
                            'version_command': [PYTHON, '-m', 'tests.fixtures_pkg.interop_udp_echo_server', '--version'],
                        },
                        'assertions': [
                            {'path': 'sut.exit_code', 'equals': 0},
                            {'path': 'artifacts.packet_trace.exists', 'equals': True},
                            {'path': 'artifacts.packet_trace.size', 'greater_or_equal': 1},
                            {'path': 'artifacts.qlog.exists', 'equals': True},
                            {'path': 'negotiation.sut.alpn', 'equals': 'h3'},
                        ],
                    }
                ],
            }
        )
        with tempfile.TemporaryDirectory() as artifact_root:
            runner = ExternalInteropRunner(matrix=load_external_matrix(matrix_path), artifact_root=artifact_root, source_root=ROOT)
            summary = runner.run()
            self.assertEqual(summary.passed, 1)
            result = summary.scenarios[0]
            qlog = json.loads((Path(result.artifact_dir) / 'qlog.json').read_text(encoding='utf-8'))
            self.assertEqual(qlog['traces'][0]['vantage_point']['type'], 'network')
            packet_events = [event for event in qlog['traces'][0]['events'] if event[2].startswith('packet_')]
            self.assertTrue(packet_events)
            self.assertEqual(packet_events[0][3]['packets'][0]['packet_type'], 'initial')

    def test_failed_assertions_are_recorded(self):
        matrix_path = self._write_matrix(
            {
                'name': 'failure-path',
                'scenarios': [
                    {
                        'id': 'http1-failure-recording',
                        'protocol': 'http1',
                        'role': 'server',
                        'feature': 'post-echo',
                        'peer': 'fixture-http-client',
                        'sut': {
                            'name': 'tigrcorn-http1',
                            'adapter': 'subprocess',
                            'role': 'server',
                            'command': [PYTHON, '-m', 'tigrcorn', 'examples.echo_http.app:app', '--host', '{bind_host}', '--port', '{bind_port}', '--protocol', 'http1', '--disable-websocket', '--no-access-log', '--lifespan', 'off'],
                            'ready_pattern': 'listening on',
                            'version_command': [PYTHON, '-m', 'tigrcorn', '--help'],
                        },
                        'peer_process': {
                            'name': 'fixture-http-client',
                            'adapter': 'subprocess',
                            'role': 'client',
                            'command': [PYTHON, '-m', 'tests.fixtures_pkg.interop_http_client'],
                            'version_command': [PYTHON, '-m', 'tests.fixtures_pkg.interop_http_client', '--version'],
                        },
                        'assertions': [{'path': 'transcript.peer.response.status', 'equals': 201}],
                    }
                ],
            }
        )
        with tempfile.TemporaryDirectory() as artifact_root:
            runner = ExternalInteropRunner(matrix=load_external_matrix(matrix_path), artifact_root=artifact_root, source_root=ROOT)
            summary = runner.run()
        self.assertEqual(summary.failed, 1)
        result = summary.scenarios[0]
        self.assertFalse(result.passed)
        self.assertTrue(result.assertions_failed)
        self.assertIn('expected 201', result.assertions_failed[0])

    def test_environment_manifest_uses_env_commit_override(self):
        prior = os.environ.get('TIGRCORN_COMMIT_HASH')
        os.environ['TIGRCORN_COMMIT_HASH'] = 'feedface1234'
        try:
            manifest = build_environment_manifest(ROOT)
        finally:
            if prior is None:
                os.environ.pop('TIGRCORN_COMMIT_HASH', None)
            else:
                os.environ['TIGRCORN_COMMIT_HASH'] = prior
        self.assertEqual(manifest['tigrcorn']['commit_hash'], 'feedface1234')
        self.assertIn('python', manifest)
        self.assertIn('tools', manifest)


if __name__ == '__main__':
    unittest.main()
