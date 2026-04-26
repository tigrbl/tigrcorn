from __future__ import annotations

import json
import unittest
from pathlib import Path

from tigrcorn.config import list_blessed_profiles, resolve_effective_defaults


ROOT = Path(__file__).resolve().parents[1]


class DefaultAuditTests(unittest.TestCase):
    def _load_json(self, relative_path: str) -> dict:
        return json.loads((ROOT / relative_path).read_text(encoding='utf-8'))

    def test_default_audit_matches_runtime_resolve_effective_defaults(self):
        generated = self._load_json('DEFAULT_AUDIT.json')
        runtime = resolve_effective_defaults('default')
        self.assertEqual(generated['claim_id'], 'TC-AUDIT-DEFAULT-BASE')
        self.assertEqual(generated['effective_defaults_flat'], runtime['effective_defaults_flat'])
        self.assertEqual(generated['normalization_backfills_flat'], runtime['normalization_backfills_flat'])

    def test_profile_default_audits_match_runtime(self):
        for profile in list_blessed_profiles():
            generated = self._load_json(f'.ssot/reports/profile-defaults/{profile}.json')
            runtime = resolve_effective_defaults(profile)
            self.assertEqual(generated['claim_id'], 'TC-AUDIT-PROFILE-EFFECTIVE-DEFAULTS')
            self.assertEqual(generated['effective_defaults_flat'], runtime['effective_defaults_flat'])
            self.assertEqual(generated['profile_overlays_flat'], runtime['profile_overlays_flat'])

    def test_flag_contracts_are_reviewed_and_synced_to_default_audit(self):
        contracts = self._load_json('docs/review/conformance/flag_contracts.json')
        audit = self._load_json('DEFAULT_AUDIT.json')
        defaults_by_path = audit['effective_defaults_flat']
        self.assertTrue(contracts['phase2_review']['reviewed'])
        self.assertEqual(contracts['phase2_review']['review_status'], 'reviewed_phase2')
        for row in contracts['contracts']:
            self.assertTrue(row['phase2_review']['reviewed'])
            path = row['config_path'].replace('listeners[]', 'listeners[0]')
            self.assertEqual(row['default'], defaults_by_path.get(path))
            self.assertIn('help_text', row)
            self.assertIn('parser_default', row)

    def test_default_audit_keeps_unsafe_defaults_denied(self):
        audit = self._load_json('DEFAULT_AUDIT.json')
        flat = audit['effective_defaults_flat']
        self.assertEqual(flat['http.connect_policy'], 'deny')
        self.assertEqual(flat['quic.early_data_policy'], 'deny')
        self.assertEqual(flat['http.enable_h2c'], False)
        self.assertEqual(flat['proxy.include_server_header'], False)
        self.assertEqual(flat['websocket.enabled'], False)


if __name__ == '__main__':
    unittest.main()
