
from __future__ import annotations

import json
from pathlib import Path

import pytest
ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = ROOT / 'docs/review/conformance/intermediary_proxy_corpus_minimum_certified'


def test_index_declares_minimum_certified_corpus() -> None:
    payload = json.loads((CORPUS_ROOT / 'index.json').read_text(encoding='utf-8'))
    assert payload['corpus_kind'] == 'minimum_certified_intermediary_proxy_corpus'
    assert payload['minimum_certified_case_count'] == 3
    assert payload['supplemental_case_count'] == 9
def test_independent_cases_exist_for_http1_http2_http3() -> None:
    ids = {
        'http11-curl-origin-form-post-certified',
        'http2-h2-origin-form-post-certified',
        'http3-aioquic-origin-form-post-certified',
    }
    for case_id in ids:
        case_dir = CORPUS_ROOT / 'cases' / case_id
        metadata = json.loads((case_dir / 'corpus_metadata.json').read_text(encoding='utf-8'))
        result = json.loads((case_dir / 'result.json').read_text(encoding='utf-8'))
        assert metadata['minimum_certified']
        assert metadata['source_kind'] == 'independent_artifact'
        assert result['passed']
def test_supplemental_local_vector_cases_exist() -> None:
    for case_id in (
        'http11-connect-relay-local-vector',
        'http2-trailer-fields-local-vector',
        'http3-content-coding-local-vector',
    ):
        case_dir = CORPUS_ROOT / 'cases' / case_id
        metadata = json.loads((case_dir / 'corpus_metadata.json').read_text(encoding='utf-8'))
        vector = json.loads((case_dir / 'source_local_vector.json').read_text(encoding='utf-8'))
        assert not (metadata['minimum_certified'])
        assert metadata['source_kind'] == 'local_vector'
        assert 'name' in vector
