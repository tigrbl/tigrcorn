from __future__ import annotations

import json
import unittest
from pathlib import Path

from tigrcorn.config.negative_surface import FAIL_STATE_REGISTRY, NEGATIVE_CORPORA
from tools.cert.negative_surface import generate as generate_negative_surface


class Phase7NegativeCertificationTests(unittest.TestCase):
    def test_generated_registry_and_corpora_match_metadata(self) -> None:
        generate_negative_surface()
        registry = json.loads(Path('docs/conformance/fail_state_registry.json').read_text(encoding='utf-8'))
        corpora = json.loads(Path('docs/conformance/negative_corpora.json').read_text(encoding='utf-8'))
        self.assertEqual(registry['registry'], FAIL_STATE_REGISTRY)
        self.assertEqual(corpora['corpora'], NEGATIVE_CORPORA)
        self.assertIn('strip_and_continue', Path('docs/conformance/fail_state_registry.md').read_text(encoding='utf-8'))

    def test_expected_outcome_bundles_exist_for_all_surfaces_and_preserved_artifacts_resolve(self) -> None:
        generate_negative_surface()
        bundle_index = json.loads(Path('docs/conformance/negative_bundles.json').read_text(encoding='utf-8'))
        surfaces = {row['surface'] for row in bundle_index['bundles']}
        self.assertEqual(surfaces, set(NEGATIVE_CORPORA))
        for bundle in bundle_index['bundles']:
            bundle_path = Path(bundle['path'])
            self.assertTrue(bundle_path.exists(), msg=bundle_path)
            payload = json.loads(bundle_path.read_text(encoding='utf-8'))
            self.assertEqual(payload['surface'], bundle['surface'])
            for case in payload['cases']:
                for artifact in case['preserved_artifacts']:
                    self.assertTrue(Path(artifact).exists(), msg=artifact)

    def test_phase7_surfaces_cover_all_requested_risky_areas(self) -> None:
        registry_surfaces = {row['surface'] for row in FAIL_STATE_REGISTRY}
        self.assertEqual(
            registry_surfaces,
            {'proxy', 'early_data', 'quic', 'origin', 'connect_relay', 'tls_x509', 'mixed_topology'},
        )


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
