from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = ROOT / 'docs/review/conformance/intermediary_proxy_corpus'


class IntermediaryProxyCorpusTests(unittest.TestCase):
    def test_index_lists_seed_corpus_cases(self) -> None:
        payload = json.loads((CORPUS_ROOT / 'index.json').read_text(encoding='utf-8'))
        ids = {entry['id'] for entry in payload['cases']}
        self.assertEqual(
            ids,
            {
                'http11-curl-origin-form-post',
                'http11-connect-relay-local-vector',
                'http2-connect-relay-local-vector',
                'http3-connect-relay-local-vector',
            },
        )

    def test_http11_seed_case_preserves_third_party_artifacts(self) -> None:
        case_dir = CORPUS_ROOT / 'cases' / 'http11-curl-origin-form-post'
        metadata = json.loads((case_dir / 'corpus_metadata.json').read_text(encoding='utf-8'))
        result = json.loads((case_dir / 'result.json').read_text(encoding='utf-8'))
        self.assertEqual(metadata['source_kind'], 'independent_artifact')
        self.assertEqual(metadata['peer'], 'curl')
        self.assertTrue(result['passed'])

    def test_connect_cases_preserve_local_vector_metadata(self) -> None:
        for carrier in ('http11', 'http2', 'http3'):
            case_dir = CORPUS_ROOT / 'cases' / f'{carrier}-connect-relay-local-vector'
            metadata = json.loads((case_dir / 'corpus_metadata.json').read_text(encoding='utf-8'))
            vector = json.loads((case_dir / 'source_local_vector.json').read_text(encoding='utf-8'))
            self.assertEqual(metadata['source_kind'], 'local_vector')
            self.assertEqual(vector['name'], 'http-connect-relay')
