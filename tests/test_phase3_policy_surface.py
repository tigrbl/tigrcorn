from __future__ import annotations

import argparse
import json
import unittest
from pathlib import Path

from tigrcorn.cli import build_parser
from tigrcorn.config.env import load_env_config
from tigrcorn.config.policy_surface import POLICY_GROUPS, PROXY_CONTRACT, flag_help
from tigrcorn.utils.proxy import resolve_proxy_view


ROOT = Path(__file__).resolve().parents[1]


class Phase3PolicySurfaceTests(unittest.TestCase):
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

    def test_generated_policy_surface_matches_metadata_and_help(self):
        payload = self._load_json('docs/conformance/policy_surface.json')
        parser_rows = self._parser_rows()
        self.assertEqual(len(payload['groups']), len(POLICY_GROUPS))
        generated_by_claim = {row['claim_id']: row for row in payload['groups']}
        for group in POLICY_GROUPS:
            generated = generated_by_claim[group['claim_id']]
            self.assertEqual(generated['flags'], group['flags'])
            self.assertEqual(generated['carriers'], group['carriers'])
            for row in generated['rows']:
                self.assertEqual(row['help_text'], parser_rows[row['flag']].help)
                self.assertEqual(row['help_text'], flag_help(row['flag'], parser_rows[row['flag']].help))

    def test_proxy_contract_json_matches_metadata(self):
        payload = self._load_json('docs/conformance/proxy_contract.json')
        self.assertEqual(payload['trust'], PROXY_CONTRACT['trust'])
        self.assertEqual(payload['precedence'], PROXY_CONTRACT['precedence'])
        self.assertEqual(payload['normalization'], PROXY_CONTRACT['normalization'])

    def test_forwarded_precedence_beats_x_forwarded_when_peer_is_trusted(self):
        view = resolve_proxy_view(
            [
                (b'forwarded', b'for=198.51.100.10:8443;proto=https;host=forwarded.example:9443;path=/edge'),
                (b'x-forwarded-for', b'203.0.113.7'),
                (b'x-forwarded-proto', b'http'),
                (b'x-forwarded-host', b'legacy.example'),
                (b'x-forwarded-prefix', b'/legacy'),
            ],
            client=('127.0.0.1', 5000),
            server=('127.0.0.1', 8000),
            scheme='http',
            root_path='/svc',
            enabled=True,
            forwarded_allow_ips=('127.0.0.1',),
        )
        self.assertEqual(view.client, ('198.51.100.10', 8443))
        self.assertEqual(view.scheme, 'https')
        self.assertEqual(view.server, ('forwarded.example', 9443))
        self.assertEqual(view.root_path, '/svc/edge')

    def test_x_forwarded_fallback_applies_when_forwarded_is_absent(self):
        view = resolve_proxy_view(
            [
                (b'x-forwarded-for', b'203.0.113.8'),
                (b'x-forwarded-proto', b'https'),
                (b'x-forwarded-host', b'example.com'),
                (b'x-forwarded-prefix', b'/svc'),
            ],
            client=('127.0.0.1', 5001),
            server=('127.0.0.1', 8000),
            scheme='http',
            root_path='',
            enabled=True,
            forwarded_allow_ips=('127.0.0.1',),
        )
        self.assertEqual(view.client, ('203.0.113.8', 5001))
        self.assertEqual(view.scheme, 'https')
        self.assertEqual(view.server, ('example.com', 8000))
        self.assertEqual(view.root_path, '/svc')

    def test_untrusted_proxy_headers_are_ignored(self):
        view = resolve_proxy_view(
            [
                (b'forwarded', b'for=198.51.100.10;proto=https;host=example.net;path=/edge'),
                (b'x-forwarded-prefix', b'/svc'),
            ],
            client=('198.51.100.20', 5002),
            server=('127.0.0.1', 8000),
            scheme='http',
            root_path='/base',
            enabled=True,
            forwarded_allow_ips=('127.0.0.1',),
        )
        self.assertEqual(view.client, ('198.51.100.20', 5002))
        self.assertEqual(view.scheme, 'http')
        self.assertEqual(view.server, ('127.0.0.1', 8000))
        self.assertEqual(view.root_path, '/base')

    def test_env_support_covers_phase3_public_policy_fields(self):
        payload = load_env_config(
            'TIGRCORN',
            environ={
                'TIGRCORN_PROXY_HEADERS': 'true',
                'TIGRCORN_FORWARDED_ALLOW_IPS': '127.0.0.1,10.0.0.0/8',
                'TIGRCORN_ENABLE_H2C': 'false',
                'TIGRCORN_LIMIT_CONCURRENCY': '11',
                'TIGRCORN_WEBSOCKET_PING_INTERVAL': '20',
                'TIGRCORN_WEBSOCKET_PING_TIMEOUT': '5',
            },
        )
        self.assertTrue(payload['proxy']['proxy_headers'])
        self.assertEqual(payload['proxy']['forwarded_allow_ips'], ['127.0.0.1', '10.0.0.0/8'])
        self.assertFalse(payload['http']['enable_h2c'])
        self.assertEqual(payload['scheduler']['limit_concurrency'], 11)
        self.assertEqual(payload['websocket']['ping_interval'], 20)
        self.assertEqual(payload['websocket']['ping_timeout'], 5)


if __name__ == '__main__':
    unittest.main()
