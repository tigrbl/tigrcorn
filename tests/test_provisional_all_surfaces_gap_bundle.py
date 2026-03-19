from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE_ROOT = ROOT / 'docs/review/conformance/releases/0.3.6/release-0.3.6'
PROVISIONAL_ROOT = RELEASE_ROOT / 'tigrcorn-provisional-all-surfaces-gap-bundle'
STRICT_BOUNDARY = ROOT / 'docs/review/conformance/certification_boundary.all_surfaces_independent.json'
EXPECTED_SCENARIOS = {
    'websocket-http11-server-websockets-client-permessage-deflate': 'websocket-permessage-deflate',
    'websocket-http2-server-h2-client-permessage-deflate': 'websocket-permessage-deflate',
    'websocket-http3-server-aioquic-client-permessage-deflate': 'websocket-permessage-deflate',
    'http11-connect-relay-curl-client': 'http-connect-relay',
    'http2-connect-relay-h2-client': 'http-connect-relay',
    'http3-connect-relay-aioquic-client': 'http-connect-relay',
    'http11-trailer-fields-curl-client': 'http-trailer-fields',
    'http2-trailer-fields-h2-client': 'http-trailer-fields',
    'http3-trailer-fields-aioquic-client': 'http-trailer-fields',
    'http11-content-coding-curl-client': 'http-content-coding',
    'http2-content-coding-curl-client': 'http-content-coding',
    'http3-content-coding-aioquic-client': 'http-content-coding',
    'tls-server-ocsp-validation-openssl-client': 'ocsp-revocation-validation',
}


class ProvisionalAllSurfacesGapBundleTests(unittest.TestCase):
    def test_bundle_index_registers_relative_non_certifying_bundle(self) -> None:
        payload = json.loads((RELEASE_ROOT / 'bundle_index.json').read_text(encoding='utf-8'))
        provisional = payload['bundles']['provisional_all_surfaces_gap_bundle']
        self.assertEqual(
            provisional,
            'docs/review/conformance/releases/0.3.6/release-0.3.6/tigrcorn-provisional-all-surfaces-gap-bundle',
        )
        self.assertIn('all-surfaces gap bundle', '\n'.join(payload['notes']))

    def test_mapping_file_covers_all_strict_profile_scenarios(self) -> None:
        mapping_payload = json.loads((PROVISIONAL_ROOT / 'scenario_mapping.json').read_text(encoding='utf-8'))
        mappings = {entry['provisional_id']: entry['source_local_vector'] for entry in mapping_payload['mappings']}
        self.assertEqual(mappings, EXPECTED_SCENARIOS)

    def test_each_provisional_result_is_explicitly_ineligible_for_release_gates(self) -> None:
        for scenario_id, source_vector in EXPECTED_SCENARIOS.items():
            result = json.loads((PROVISIONAL_ROOT / scenario_id / 'result.json').read_text(encoding='utf-8'))
            metadata = json.loads((PROVISIONAL_ROOT / scenario_id / 'provisional_metadata.json').read_text(encoding='utf-8'))
            vector = json.loads((PROVISIONAL_ROOT / scenario_id / 'source_local_vector.json').read_text(encoding='utf-8'))
            self.assertTrue(result['passed'])
            self.assertTrue(result['provisional_non_certifying_substitution'])
            self.assertFalse(result['release_gate_eligible'])
            self.assertTrue(result['strict_profile_only'])
            self.assertEqual(result['source_local_conformance_vector'], source_vector)
            self.assertEqual(metadata['source_local_conformance_vector'], source_vector)
            self.assertFalse(metadata['release_gate_eligible'])
            self.assertTrue(result['artifact_dir'].startswith('docs/review/conformance/releases/0.3.6/release-0.3.6/'))
            self.assertEqual(vector['name'], source_vector)

    def test_strict_boundary_records_independent_tier_for_policy_bounded_rfcs(self) -> None:
        payload = json.loads(STRICT_BOUNDARY.read_text(encoding='utf-8'))
        self.assertFalse(payload['authoritative'])
        self.assertEqual(payload['derived_from'], 'docs/review/conformance/certification_boundary.json')
        for rfc in ('RFC 7692', 'RFC 9110 §9.3.6', 'RFC 9110 §6.5', 'RFC 9110 §8', 'RFC 6960'):
            self.assertEqual(payload['required_rfc_evidence'][rfc]['highest_required_evidence_tier'], 'independent_certification')


if __name__ == '__main__':
    unittest.main()
