
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = ROOT / 'docs/review/conformance/intermediary_proxy_corpus_minimum_certified'

class Phase5IntermediaryProxyCorpusTests(unittest.TestCase):
    def test_index_declares_minimum_certified_corpus(self) -> None:
        payload = json.loads((CORPUS_ROOT / 'index.json').read_text(encoding='utf-8'))
        self.assertEqual(payload['corpus_kind'], 'minimum_certified_intermediary_proxy_corpus')
        self.assertEqual(payload['minimum_certified_case_count'], 3)
        self.assertEqual(payload['supplemental_case_count'], 9)

    def test_independent_cases_exist_for_http1_http2_http3(self) -> None:
        ids = {
            'http11-curl-origin-form-post-certified',
            'http2-h2-origin-form-post-certified',
            'http3-aioquic-origin-form-post-certified',
        }
        for case_id in ids:
            case_dir = CORPUS_ROOT / 'cases' / case_id
            metadata = json.loads((case_dir / 'corpus_metadata.json').read_text(encoding='utf-8'))
            result = json.loads((case_dir / 'result.json').read_text(encoding='utf-8'))
            self.assertTrue(metadata['minimum_certified'])
            self.assertEqual(metadata['source_kind'], 'independent_artifact')
            self.assertTrue(result['passed'])

    def test_supplemental_local_vector_cases_exist(self) -> None:
        for case_id in (
            'http11-connect-relay-local-vector',
            'http2-trailer-fields-local-vector',
            'http3-content-coding-local-vector',
        ):
            case_dir = CORPUS_ROOT / 'cases' / case_id
            metadata = json.loads((case_dir / 'corpus_metadata.json').read_text(encoding='utf-8'))
            vector = json.loads((case_dir / 'source_local_vector.json').read_text(encoding='utf-8'))
            self.assertFalse(metadata['minimum_certified'])
            self.assertEqual(metadata['source_kind'], 'local_vector')
            self.assertIn('name', vector)

if __name__ == '__main__':
    unittest.main()
