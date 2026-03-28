from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tigrcorn.compat.interop_runner import ExternalInteropRunner, load_external_matrix

ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT / 'docs/review/conformance/external_matrix.release.json'
RELEASE_ROOT = ROOT / 'docs/review/conformance/releases/0.3.9/release-0.3.9/tigrcorn-independent-certification-release-matrix'
EXPECTED_ENABLED_SCENARIO_IDS = {
    'http1-server-curl-client',
    'http11-connect-relay-curl-client',
    'http11-content-coding-curl-client',
    'http11-trailer-fields-curl-client',
    'http2-connect-relay-h2-client',
    'http2-content-coding-curl-client',
    'http2-server-curl-client',
    'http2-server-h2-client',
    'http2-tls-server-curl-client',
    'http2-tls-server-h2-client',
    'http2-trailer-fields-h2-client',
    'http3-connect-relay-aioquic-client',
    'http3-content-coding-aioquic-client',
    'http3-server-aioquic-client-post',
    'http3-server-aioquic-client-post-goaway-qpack',
    'http3-server-aioquic-client-post-migration',
    'http3-server-aioquic-client-post-mtls',
    'http3-server-aioquic-client-post-resumption',
    'http3-server-aioquic-client-post-retry',
    'http3-server-aioquic-client-post-zero-rtt',
    'http3-server-openssl-quic-handshake',
    'http3-trailer-fields-aioquic-client',
    'tls-server-ocsp-validation-openssl-client',
    'websocket-http11-server-websockets-client-permessage-deflate',
    'websocket-http2-server-h2-client',
    'websocket-http2-server-h2-client-permessage-deflate',
    'websocket-http3-server-aioquic-client',
    'websocket-http3-server-aioquic-client-mtls',
    'websocket-http3-server-aioquic-client-permessage-deflate',
    'websocket-server-websockets-client',
}
EXPECTED_PENDING_SCENARIO_IDS: set[str] = set()


def _openssl_supports_quic() -> bool:
    executable = shutil.which('openssl')
    if executable is None:
        return False
    completed = subprocess.run([executable, 's_client', '-help'], capture_output=True, text=True, timeout=10.0)
    help_text = '\n'.join(part for part in (completed.stdout, completed.stderr) if part)
    return '-quic' in help_text


class ExternalIndependentPeerReleaseMatrixTests(unittest.TestCase):
    def test_release_matrix_document_covers_enabled_and_pending_independent_peers(self):
        matrix = load_external_matrix(MATRIX_PATH)
        self.assertEqual(matrix.name, 'tigrcorn-independent-certification-release-matrix')
        self.assertEqual({scenario.id for scenario in matrix.enabled_scenarios}, EXPECTED_ENABLED_SCENARIO_IDS)
        self.assertEqual(set(matrix.metadata['preserved_enabled_scenarios']), EXPECTED_ENABLED_SCENARIO_IDS)
        self.assertEqual(set(matrix.metadata['pending_third_party_http3_scenarios']), EXPECTED_PENDING_SCENARIO_IDS)
        self.assertEqual(matrix.metadata['evidence_tier'], 'independent_certification')
        self.assertIn('aioquic', matrix.metadata['independent_peers'])
        self.assertTrue(all(s.peer_process.provenance_kind != 'same_stack_fixture' for s in matrix.scenarios))

        by_id = {scenario.id: scenario for scenario in matrix.scenarios}
        for scenario_id in EXPECTED_PENDING_SCENARIO_IDS:
            scenario = by_id[scenario_id]
            self.assertFalse(scenario.enabled)
            self.assertEqual(scenario.peer_process.provenance_kind, 'third_party_library')
            self.assertEqual(scenario.peer_process.implementation_source, 'aioquic')

        for scenario_id in EXPECTED_ENABLED_SCENARIO_IDS:
            scenario = by_id[scenario_id]
            self.assertTrue(scenario.enabled)

    def test_committed_release_artifact_bundle_is_present_and_passing_for_enabled_scenarios(self):
        self.assertTrue(RELEASE_ROOT.exists())
        index_payload = json.loads((RELEASE_ROOT / 'index.json').read_text(encoding='utf-8'))
        manifest_payload = json.loads((RELEASE_ROOT / 'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(index_payload['total'], 30)
        self.assertEqual(index_payload['passed'], 30)
        self.assertEqual(index_payload['failed'], 0)
        self.assertEqual(manifest_payload['environment']['tigrcorn']['commit_hash'], 'release-0.3.9')
        self.assertEqual(manifest_payload['environment']['tigrcorn']['version'], '0.3.9')
        self.assertEqual(manifest_payload['bundle_kind'], 'independent_certification')
        self.assertIn('0.3.2', ''.join(manifest_payload['source_bundles']))
        self.assertIn('0.3.6-rfc-hardening', ''.join(manifest_payload['source_bundles']))
        self.assertIn('0.3.6-current', ''.join(manifest_payload['source_bundles']))

        scenarios = {item['id']: item for item in index_payload['scenarios']}
        self.assertEqual(set(scenarios), EXPECTED_ENABLED_SCENARIO_IDS)

        http2_tls_result = json.loads((RELEASE_ROOT / 'http2-tls-server-curl-client' / 'result.json').read_text(encoding='utf-8'))
        self.assertTrue(http2_tls_result['passed'])
        self.assertEqual(http2_tls_result['negotiation']['peer']['protocol'], 'h2')

        websocket_h2_result = json.loads((RELEASE_ROOT / 'websocket-http2-server-h2-client' / 'result.json').read_text(encoding='utf-8'))
        self.assertTrue(websocket_h2_result['passed'])
        self.assertTrue(websocket_h2_result['negotiation']['peer']['settings_enable_connect_protocol'])

        quic_artifact_dir = RELEASE_ROOT / 'http3-server-openssl-quic-handshake'
        self.assertTrue((quic_artifact_dir / 'qlog.json').exists())
        quic_result = json.loads((quic_artifact_dir / 'result.json').read_text(encoding='utf-8'))
        self.assertTrue(quic_result['passed'])
        self.assertEqual(quic_result['negotiation']['peer']['protocol'], 'QUICv1')
        self.assertEqual(quic_result['negotiation']['peer']['alpn'], 'h3')
        self.assertEqual(quic_result['negotiation']['peer']['verification'], 'OK')

    def test_release_matrix_can_be_replayed_with_local_independent_peers(self):
        if os.environ.get('TIGRCORN_RUN_EXTERNAL_RELEASE_MATRIX') != '1':
            self.skipTest('set TIGRCORN_RUN_EXTERNAL_RELEASE_MATRIX=1 to rerun the enabled independent-peer matrix')
        if shutil.which('curl') is None:
            self.skipTest('curl is not available')
        if not _openssl_supports_quic():
            self.skipTest('OpenSSL QUIC support is not available')
        if importlib.util.find_spec('websockets') is None:
            self.skipTest('websockets is not available')
        if importlib.util.find_spec('h2') is None:
            self.skipTest('python-h2 is not available')

        with tempfile.TemporaryDirectory() as artifact_root:
            prior = os.environ.get('TIGRCORN_COMMIT_HASH')
            os.environ['TIGRCORN_COMMIT_HASH'] = 'test-independent-peer-release-matrix'
            try:
                runner = ExternalInteropRunner(
                    matrix=load_external_matrix(MATRIX_PATH),
                    artifact_root=artifact_root,
                    source_root=ROOT,
                )
                summary = runner.run()
            finally:
                if prior is None:
                    os.environ.pop('TIGRCORN_COMMIT_HASH', None)
                else:
                    os.environ['TIGRCORN_COMMIT_HASH'] = prior

        self.assertEqual(summary.total, len(EXPECTED_ENABLED_SCENARIO_IDS))
        self.assertEqual(summary.passed, len(EXPECTED_ENABLED_SCENARIO_IDS))
        self.assertEqual(summary.failed, 0)
        self.assertEqual({item.scenario_id for item in summary.scenarios}, EXPECTED_ENABLED_SCENARIO_IDS)


if __name__ == '__main__':
    unittest.main()
