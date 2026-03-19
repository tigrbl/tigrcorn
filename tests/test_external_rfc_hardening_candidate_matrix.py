from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from tigrcorn.compat.interop_runner import ExternalInteropRunner, load_external_matrix

ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT / 'docs/review/conformance/external_matrix.rfc_hardening_candidate.json'
RELEASE_ROOT = ROOT / 'docs/review/conformance/releases/0.3.6-rfc-hardening/release-0.3.6-rfc-hardening/tigrcorn-rfc-hardening-candidate-matrix'
EXPECTED_SCENARIO_IDS = {
    'http2-tls-server-curl-client',
    'websocket-http2-server-h2-client',
}


class ExternalRfcHardeningCandidateMatrixTests(unittest.TestCase):
    def test_candidate_matrix_document_covers_added_http2_independent_peers(self):
        matrix = load_external_matrix(MATRIX_PATH)
        self.assertEqual(matrix.name, 'tigrcorn-rfc-hardening-candidate-matrix')
        self.assertEqual({scenario.id for scenario in matrix.scenarios}, EXPECTED_SCENARIO_IDS)
        self.assertEqual({scenario.peer for scenario in matrix.scenarios}, {'curl', 'python-h2'})

    def test_committed_candidate_artifact_bundle_is_present_and_passing(self):
        self.assertTrue(RELEASE_ROOT.exists())
        index_payload = json.loads((RELEASE_ROOT / 'index.json').read_text(encoding='utf-8'))
        manifest_payload = json.loads((RELEASE_ROOT / 'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(index_payload['total'], 2)
        self.assertEqual(index_payload['passed'], 2)
        self.assertEqual(index_payload['failed'], 0)
        self.assertEqual(manifest_payload['environment']['tigrcorn']['commit_hash'], 'release-0.3.6-rfc-hardening')
        self.assertEqual(manifest_payload['environment']['tigrcorn']['version'], '0.3.6')
        self.assertIn('curl', manifest_payload['environment']['tools'])

        scenarios = {item['id']: item for item in index_payload['scenarios']}
        self.assertEqual(set(scenarios), EXPECTED_SCENARIO_IDS)
        for scenario_id in EXPECTED_SCENARIO_IDS:
            result = json.loads((RELEASE_ROOT / scenario_id / 'result.json').read_text(encoding='utf-8'))
            self.assertTrue(result['passed'])
            self.assertTrue((RELEASE_ROOT / scenario_id / 'packet_trace.jsonl').exists())
            self.assertTrue((RELEASE_ROOT / scenario_id / 'peer_transcript.json').exists())
            self.assertEqual(result['peer']['exit_code'], 0)

    def test_candidate_matrix_can_be_replayed_with_local_independent_peers(self):
        if os.environ.get('TIGRCORN_RUN_EXTERNAL_RFC_HARDENING_MATRIX') != '1':
            self.skipTest('set TIGRCORN_RUN_EXTERNAL_RFC_HARDENING_MATRIX=1 to rerun the HTTP/2 hardening matrix')
        if shutil.which('curl') is None:
            self.skipTest('curl is not available')
        if importlib.util.find_spec('h2') is None:
            self.skipTest('python-h2 is not available')

        with tempfile.TemporaryDirectory() as artifact_root:
            prior = os.environ.get('TIGRCORN_COMMIT_HASH')
            os.environ['TIGRCORN_COMMIT_HASH'] = 'test-rfc-hardening-candidate-matrix'
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

        self.assertEqual(summary.total, 2)
        self.assertEqual(summary.passed, 2)
        self.assertEqual(summary.failed, 0)
        self.assertEqual({item.scenario_id for item in summary.scenarios}, EXPECTED_SCENARIO_IDS)


if __name__ == '__main__':
    unittest.main()
