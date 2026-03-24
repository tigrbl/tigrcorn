from __future__ import annotations

import importlib.util
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from tigrcorn.compat.interop_runner import ExternalInteropRunner, load_external_matrix, summarize_matrix_dimensions

ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT / 'docs/review/conformance/external_matrix.current_release.json'
RELEASE_ROOT = ROOT / 'docs/review/conformance/releases/0.3.8/release-0.3.8/tigrcorn-mixed-compatibility-release-matrix'
EXPECTED_SCENARIO_IDS = {
    'http1-server-curl-client',
    'http2-server-h2-client',
    'http2-tls-server-h2-client',
    'websocket-server-websockets-client',
    'websocket-http2-server-h2-client',
    'http3-server-public-client-post',
    'http3-server-public-client-post-mtls',
    'http3-server-public-client-post-retry',
    'http3-server-public-client-post-resumption',
    'http3-server-public-client-post-zero-rtt',
    'http3-server-public-client-post-migration',
    'http3-server-public-client-post-goaway-qpack',
    'websocket-http3-server-public-client',
    'websocket-http3-server-public-client-mtls',
}


class ExternalCurrentReleaseMatrixTests(unittest.TestCase):
    def test_current_release_matrix_document_covers_expected_peers_and_dimensions(self):
        matrix = load_external_matrix(MATRIX_PATH)
        self.assertEqual(matrix.name, 'tigrcorn-current-release-matrix')
        self.assertEqual({scenario.id for scenario in matrix.scenarios}, EXPECTED_SCENARIO_IDS)
        self.assertEqual({scenario.peer for scenario in matrix.scenarios}, {'curl', 'python-h2', 'tigrcorn-public-client', 'websockets'})
        self.assertEqual(matrix.metadata['evidence_tier'], 'mixed')
        self.assertEqual(matrix.metadata['canonical_release_root'], 'docs/review/conformance/releases/0.3.8/release-0.3.8/tigrcorn-mixed-compatibility-release-matrix')
        self.assertEqual({scenario.evidence_tier for scenario in matrix.scenarios}, {'independent_certification', 'same_stack_replay'})
        self.assertTrue(all(s.peer_process.provenance_kind == 'same_stack_fixture' for s in matrix.scenarios if s.peer == 'tigrcorn-public-client'))

        dimensions = summarize_matrix_dimensions(matrix)
        self.assertEqual(dimensions['evidence_tier'], ['independent_certification', 'same_stack_replay'])
        self.assertEqual(dimensions['retry'], [False, True])
        self.assertEqual(dimensions['resumption'], [False, True])
        self.assertEqual(dimensions['zero_rtt'], [False, True])
        self.assertEqual(dimensions['migration'], [False, True])
        self.assertEqual(dimensions['goaway'], [False, True])
        self.assertEqual(dimensions['qpack_blocking'], [False, True])

    def test_committed_current_release_artifact_bundle_is_present_and_passing(self):
        self.assertTrue(RELEASE_ROOT.exists())
        index_payload = json.loads((RELEASE_ROOT / 'index.json').read_text(encoding='utf-8'))
        manifest_payload = json.loads((RELEASE_ROOT / 'manifest.json').read_text(encoding='utf-8'))

        self.assertEqual(index_payload['total'], 14)
        self.assertEqual(index_payload['passed'], 14)
        self.assertEqual(index_payload['failed'], 0)
        self.assertEqual(manifest_payload['environment']['tigrcorn']['commit_hash'], 'release-0.3.8')
        self.assertEqual(manifest_payload['environment']['tigrcorn']['version'], '0.3.8')
        self.assertEqual(manifest_payload['bundle_kind'], 'mixed')

        scenarios = {item['id']: item for item in index_payload['scenarios']}
        self.assertEqual(set(scenarios), EXPECTED_SCENARIO_IDS)

        h2_result = json.loads((RELEASE_ROOT / 'http2-server-h2-client' / 'result.json').read_text(encoding='utf-8'))
        self.assertTrue(h2_result['passed'])
        self.assertEqual(h2_result['negotiation']['peer']['protocol'], 'h2c')
        self.assertEqual(h2_result['transcript']['peer']['response']['body'], 'echo:hello-http2')

        h3_result = json.loads((RELEASE_ROOT / 'http3-server-public-client-post' / 'result.json').read_text(encoding='utf-8'))
        self.assertTrue(h3_result['passed'])
        self.assertEqual(h3_result['negotiation']['peer']['protocol'], 'h3')
        self.assertTrue((RELEASE_ROOT / 'http3-server-public-client-post' / 'qlog.json').exists())

    def test_current_release_matrix_can_be_replayed_with_local_peers(self):
        if os.environ.get('TIGRCORN_RUN_EXTERNAL_CURRENT_RELEASE_MATRIX') != '1':
            self.skipTest('set TIGRCORN_RUN_EXTERNAL_CURRENT_RELEASE_MATRIX=1 to rerun the full current-release matrix')
        if shutil.which('curl') is None:
            self.skipTest('curl is not available')
        if importlib.util.find_spec('websockets') is None:
            self.skipTest('websockets is not available')
        if importlib.util.find_spec('h2') is None:
            self.skipTest('python-h2 is not available')

        with tempfile.TemporaryDirectory() as artifact_root:
            prior = os.environ.get('TIGRCORN_COMMIT_HASH')
            os.environ['TIGRCORN_COMMIT_HASH'] = 'test-current-release-matrix'
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

        self.assertEqual(summary.total, 14)
        self.assertEqual(summary.passed, 14)
        self.assertEqual(summary.failed, 0)
        self.assertEqual({item.scenario_id for item in summary.scenarios}, EXPECTED_SCENARIO_IDS)


if __name__ == '__main__':
    unittest.main()
