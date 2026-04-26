from __future__ import annotations

import json
import unittest
from pathlib import Path

from tigrcorn.config import build_config, list_blessed_profiles, resolve_effective_profile_mapping, resolve_profile_spec
from tigrcorn.errors import ConfigError


class ProfileResolutionTests(unittest.TestCase):
    def test_registry_exposes_phase1_blessed_profiles(self):
        self.assertEqual(
            list_blessed_profiles(),
            (
                'default',
                'strict-h1-origin',
                'strict-h2-origin',
                'strict-h3-edge',
                'strict-mtls-origin',
                'static-origin',
            ),
        )

    def test_default_profile_freezes_safe_tcp_http1_posture(self):
        config = build_config()
        self.assertEqual(config.app.profile, 'default')
        self.assertEqual(config.listeners[0].kind, 'tcp')
        self.assertEqual(config.listeners[0].enabled_protocols, ('http1',))
        self.assertFalse(config.websocket.enabled)
        self.assertFalse(config.http.enable_h2c)
        self.assertEqual(config.http.connect_policy, 'deny')
        self.assertFalse(config.proxy.include_server_header)

    def test_strict_h2_origin_requires_tls_and_h2_posture(self):
        config = build_config(
            profile='strict-h2-origin',
            ssl_certfile='cert.pem',
            ssl_keyfile='key.pem',
        )
        self.assertEqual(config.app.profile, 'strict-h2-origin')
        self.assertEqual(config.tls.alpn_protocols, ['h2'])
        self.assertEqual(config.listeners[0].enabled_protocols, ('http2',))
        self.assertTrue(config.listeners[0].ssl_enabled)

    def test_strict_h3_edge_requires_explicit_edge_posture(self):
        config = build_config(
            profile='strict-h3-edge',
            ssl_certfile='cert.pem',
            ssl_keyfile='key.pem',
        )
        self.assertEqual(config.app.profile, 'strict-h3-edge')
        self.assertTrue(config.http.alt_svc_auto)
        self.assertTrue(config.quic.require_retry)
        self.assertEqual(config.quic.early_data_policy, 'deny')
        self.assertEqual(len(config.listeners), 2)
        self.assertEqual(config.listeners[0].enabled_protocols, ('http1', 'http2'))
        self.assertEqual(config.listeners[1].enabled_protocols, ('quic', 'http3'))

    def test_strict_mtls_origin_requires_ca_bundle(self):
        with self.assertRaises(ConfigError):
            build_config(
                profile='strict-mtls-origin',
                ssl_certfile='cert.pem',
                ssl_keyfile='key.pem',
            )

        config = build_config(
            profile='strict-mtls-origin',
            ssl_certfile='cert.pem',
            ssl_keyfile='key.pem',
            ssl_ca_certs='ca.pem',
        )
        self.assertTrue(config.tls.require_client_cert)
        self.assertTrue(config.listeners[0].ssl_require_client_cert)

    def test_static_origin_requires_mount(self):
        with self.assertRaises(ConfigError):
            build_config(profile='static-origin')

        config = build_config(profile='static-origin', static_path_mount='/srv/static')
        self.assertEqual(config.static.route, '/')
        self.assertEqual(config.static.mount, '/srv/static')
        self.assertTrue(config.static.dir_to_file)

    def test_effective_profile_mapping_carries_claimed_posture(self):
        profile = resolve_effective_profile_mapping('strict-h3-edge')
        self.assertEqual(profile['app']['profile'], 'strict-h3-edge')
        self.assertEqual(profile['quic']['early_data_policy'], 'deny')
        self.assertEqual(profile['listeners'][1]['protocols'], ['quic', 'http3'])

    def test_profile_artifacts_are_generated_from_registry(self):
        bundle = json.loads(Path('docs/conformance/profile_bundles.json').read_text(encoding='utf-8'))
        self.assertEqual([item['profile_id'] for item in bundle['profiles']], list(list_blessed_profiles()))
        profile_file = json.loads(Path('src/tigrcorn/profiles/default.profile.json').read_text(encoding='utf-8'))
        self.assertEqual(profile_file['profile_id'], 'default')
        self.assertEqual(profile_file['effective_config']['app']['profile'], 'default')
        strict_bundle = resolve_profile_spec('strict-mtls-origin')
        self.assertIn('TC-PROFILE-STRICT-MTLS-ORIGIN', strict_bundle['claim_ids'])


if __name__ == '__main__':
    unittest.main()
