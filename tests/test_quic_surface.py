from __future__ import annotations

import argparse
import json
import unittest
from pathlib import Path
from types import SimpleNamespace

from tigrcorn.cli import build_parser
from tigrcorn.config.env import load_env_config
from tigrcorn.config.quic_surface import EARLY_DATA_CONTRACT, QUIC_STATE_CLAIMS, quic_flag_help
from tigrcorn.protocols.http3.handler import HTTP3DatagramHandler


ROOT = Path(__file__).resolve().parents[1]


class Phase4QuicSurfaceTests(unittest.TestCase):
    def _load_json(self, relative_path: str) -> dict:
        return json.loads((ROOT / relative_path).read_text(encoding='utf-8'))

    def _parser_rows(self) -> dict[str, argparse.Action]:
        parser = build_parser()
        rows: dict[str, argparse.Action] = {}
        for action in parser._actions:
            if isinstance(action, argparse._HelpAction):
                continue
            if action.help == argparse.SUPPRESS:
                continue
            for flag in action.option_strings:
                if flag.startswith('--'):
                    rows[flag] = action
        return rows

    def test_generated_early_data_contract_matches_metadata_and_help(self):
        payload = self._load_json('docs/conformance/early_data_contract.json')
        parser_rows = self._parser_rows()
        self.assertEqual(payload['default_policy'], EARLY_DATA_CONTRACT['default_policy'])
        self.assertEqual(payload['value_space'], EARLY_DATA_CONTRACT['value_space'])
        self.assertEqual(parser_rows['--quic-early-data-policy'].help, quic_flag_help('--quic-early-data-policy'))
        self.assertTrue(payload['evidence'])
        self.assertIn('425 Too Early', payload['replay_policy']['require_downgrade'])

    def test_generated_quic_state_tracks_required_state_claims(self):
        payload = self._load_json('docs/conformance/quic_state.json')
        generated = {row['claim_id']: row for row in payload['claims']}
        for claim in QUIC_STATE_CLAIMS:
            row = generated[claim['claim_id']]
            self.assertEqual(row['feature'], claim['feature'])
            self.assertTrue(row['scenarios'])
            self.assertTrue(all(item['evidence_tier'] == 'independent_certification' for item in row['scenarios']))

    def test_env_support_covers_phase4_quic_fields(self):
        payload = load_env_config(
            'TIGRCORN',
            environ={
                'TIGRCORN_QUIC_REQUIRE_RETRY': 'true',
                'TIGRCORN_QUIC_MAX_DATAGRAM_SIZE': '1400',
                'TIGRCORN_QUIC_IDLE_TIMEOUT': '15',
                'TIGRCORN_QUIC_EARLY_DATA_POLICY': 'require',
            },
        )
        self.assertTrue(payload['quic']['require_retry'])
        self.assertEqual(payload['quic']['max_datagram_size'], 1400)
        self.assertEqual(payload['quic']['idle_timeout'], 15)
        self.assertEqual(payload['quic']['early_data_policy'], 'require')

    def test_http3_handler_ticket_advertisement_respects_policy(self):
        handler = object.__new__(HTTP3DatagramHandler)
        session = SimpleNamespace(quic=SimpleNamespace(handshake_driver=object()))
        handler.config = SimpleNamespace(quic=SimpleNamespace(early_data_policy='deny'))
        self.assertEqual(handler._session_ticket_early_data_size(session), 0)
        handler.config = SimpleNamespace(quic=SimpleNamespace(early_data_policy='allow'))
        self.assertEqual(handler._session_ticket_early_data_size(session), 4096)

    def test_http3_handler_require_policy_triggers_too_early_on_resumed_downgrade(self):
        handler = object.__new__(HTTP3DatagramHandler)
        handler.config = SimpleNamespace(quic=SimpleNamespace(early_data_policy='require'))
        resumed = SimpleNamespace(quic=SimpleNamespace(handshake_driver=SimpleNamespace(_using_psk=True, early_data_accepted=False)))
        fresh = SimpleNamespace(quic=SimpleNamespace(handshake_driver=SimpleNamespace(_using_psk=False, early_data_accepted=False)))
        accepted = SimpleNamespace(quic=SimpleNamespace(handshake_driver=SimpleNamespace(_using_psk=True, early_data_accepted=True)))
        self.assertTrue(handler._should_send_too_early(resumed))
        self.assertFalse(handler._should_send_too_early(fresh))
        self.assertFalse(handler._should_send_too_early(accepted))


if __name__ == '__main__':
    unittest.main()
