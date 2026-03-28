from __future__ import annotations

import re
from pathlib import Path
import unittest

from tigrcorn.compat.interop import load_vectors


ROOT = Path(__file__).resolve().parents[1]
CORPUS_PATH = ROOT / 'docs/review/conformance/corpus.json'
RFC_REVIEW_PATH = ROOT / 'docs/review/rfc_compliance_review.md'
EXPECTED_VECTOR_CATALOG = {
    '7541': {'name': 'hpack-dynamic-state', 'protocol': 'http2-hpack', 'fixture': 'tests/test_http2_hpack.py'},
    '7692': {'name': 'websocket-permessage-deflate', 'protocol': 'websocket-compression', 'fixture': 'tests/test_websocket_rfc7692.py'},
    '8441': {'name': 'http2-websocket-extended-connect', 'protocol': 'http2-websocket', 'fixture': 'tests/test_http2_websocket_rfc8441.py'},
    '8446': {'name': 'tls13-package-subsystem', 'protocol': 'tls13', 'fixture': 'tests/test_tls13_engine_upgrade.py'},
    '6455': {'name': 'websocket-core', 'protocol': 'websocket', 'fixture': 'tests/test_websocket_rfc6455.py'},
    '9000': {'name': 'quic-packet-codec', 'protocol': 'quic-transport', 'fixture': 'tests/test_quic_packets_rfc9000.py'},
    '9001': {'name': 'quic-tls-initial-vectors', 'protocol': 'quic-tls', 'fixture': 'tests/test_quic_tls_rfc9001.py'},
    '9002': {'name': 'quic-recovery', 'protocol': 'quic-recovery', 'fixture': 'tests/test_quic_recovery_rfc9002.py'},
    '9110-connect': {'name': 'http-connect-relay', 'protocol': 'http-connect', 'fixture': 'tests/test_connect_rfc9110.py'},
    '9110-trailers': {'name': 'http-trailer-fields', 'protocol': 'http-trailers', 'fixture': 'tests/test_trailers_rfc9110.py'},
    '9110-content-coding': {'name': 'http-content-coding', 'protocol': 'http-content-coding', 'fixture': 'tests/test_http_content_coding_rfc9110.py'},
    '7232': {'name': 'http-conditional-requests', 'protocol': 'http-conditional', 'fixture': 'tests/test_rfc7232_conditional_requests.py'},
    '7233': {'name': 'http-byte-ranges', 'protocol': 'http-range', 'fixture': 'tests/test_rfc7233_range_requests.py'},
    '8297': {'name': 'http-early-hints', 'protocol': 'http-early-hints', 'fixture': 'tests/test_rfc8297_early_hints.py'},
    'RFC 7838 §3': {'name': 'http-alt-svc-header-advertisement', 'protocol': 'http-alt-svc', 'fixture': 'tests/test_rfc7838_alt_svc.py'},
    '9112': {'name': 'http11-server-surface', 'protocol': 'http1', 'fixture': 'tests/test_http1_rfc9112.py'},
    '9113': {'name': 'http2-server-surface', 'protocol': 'http2', 'fixture': 'tests/test_http2_rfc9113.py'},
    '9114': {'name': 'http3-server-surface', 'protocol': 'http3', 'fixture': 'tests/test_http3_rfc9114.py'},
    '9204': {'name': 'qpack-dynamic-state', 'protocol': 'http3-qpack', 'fixture': 'tests/test_qpack_completion.py'},
    '9220': {'name': 'http3-websocket-extended-connect', 'protocol': 'http3-websocket', 'fixture': 'tests/test_http3_websocket_rfc9220.py'},
    '5280': {'name': 'x509-path-validation', 'protocol': 'x509-validation', 'fixture': 'tests/test_x509_webpki_validation.py'},
    '6960': {'name': 'ocsp-revocation-validation', 'protocol': 'x509-revocation', 'fixture': 'tests/test_x509_webpki_validation.py'},
    '7301': {'name': 'tls-alpn-negotiation', 'protocol': 'tls13-alpn', 'fixture': 'tests/test_tls_alpn_rfc7301.py'},
}
DOCUMENTED_RFC_EXTRAS = {'6455', '9000', '9001'}


def _load_corpus():
    return load_vectors(CORPUS_PATH)


def _base_rfc(rfc: str) -> str:
    return rfc.split('-', 1)[0]


class ConformanceCorpusTests(unittest.TestCase):
    def test_corpus_matches_expected_vector_catalog(self):
        vectors = _load_corpus()
        self.assertEqual(len(vectors), len(EXPECTED_VECTOR_CATALOG))
        seen_vector_ids: set[str] = set()
        for vector in vectors:
            self.assertNotIn(vector.rfc, seen_vector_ids, msg=vector.rfc)
            seen_vector_ids.add(vector.rfc)
            self.assertIn(vector.rfc, EXPECTED_VECTOR_CATALOG)
            expected = EXPECTED_VECTOR_CATALOG[vector.rfc]
            self.assertEqual(vector.name, expected['name'])
            self.assertEqual(vector.protocol, expected['protocol'])
            self.assertEqual(vector.fixture, expected['fixture'])
            self.assertGreaterEqual(len(vector.description.split()), 8, msg=vector.rfc)
        self.assertEqual(seen_vector_ids, set(EXPECTED_VECTOR_CATALOG))

    def test_documented_review_surface_is_a_subset_of_the_corpus(self):
        vectors = _load_corpus()
        corpus_rfcs = {_base_rfc(vector.rfc) for vector in vectors}
        documented_rfcs = set(re.findall(r'RFC\s+(\d+)', RFC_REVIEW_PATH.read_text()))
        required_rfcs = documented_rfcs | DOCUMENTED_RFC_EXTRAS
        self.assertFalse(required_rfcs - corpus_rfcs, msg=sorted(required_rfcs - corpus_rfcs))

    def test_vector_names_and_protocol_rfc_pairs_are_unique(self):
        vectors = _load_corpus()
        self.assertEqual(len({vector.name for vector in vectors}), len(vectors))
        self.assertEqual(len({(vector.protocol, vector.rfc) for vector in vectors}), len(vectors))

    def test_every_vector_points_to_a_real_test_fixture(self):
        vectors = _load_corpus()
        for vector in vectors:
            fixture = ROOT / vector.fixture
            self.assertTrue(fixture.exists(), msg=vector.fixture)
            contents = fixture.read_text()
            self.assertTrue('def test_' in contents or 'class ' in contents, msg=vector.fixture)


if __name__ == '__main__':
    unittest.main()
