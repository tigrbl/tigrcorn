from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

from tigrcorn.cli import build_parser
from tigrcorn.config.files import load_config_source
from tigrcorn.config.load import build_config_from_namespace
from tigrcorn.protocols.websocket.handshake import build_handshake_response, websocket_accept_value
from tigrcorn.static import StaticFilesApp
from tigrcorn.utils.authority import authority_allowed
from tigrcorn.utils.headers import apply_response_header_policy, get_header


class Phase1SurfaceParityCheckpointTests(unittest.TestCase):
    def test_parser_and_namespace_map_new_phase1_flags(self):
        parser = build_parser()
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / '.env.test'
            env_file.write_text('', encoding='utf-8')
            ns = parser.parse_args(
                [
                    'tests.fixtures_pkg.appmod:app',
                    '--uds', '/tmp/tigrcorn.sock',
                    '--env-file', str(env_file),
                    '--runtime', 'uvloop',
                    '--worker-healthcheck-timeout', '9.5',
                    '--user', '1000',
                    '--group', '1001',
                    '--umask', '022',
                    '--date-header',
                    '--header', 'x-phase1: enabled',
                    '--server-name', 'example.com,api.example.com',
                    '--use-colors',
                ]
            )
            config = build_config_from_namespace(ns)
        self.assertTrue(config.app.env_file.endswith('.env.test'))
        self.assertEqual(config.process.runtime, 'uvloop')
        self.assertEqual(config.process.worker_healthcheck_timeout, 9.5)
        self.assertEqual(config.listeners[0].kind, 'unix')
        self.assertEqual(config.listeners[0].user, 1000)
        self.assertEqual(config.listeners[0].group, 1001)
        self.assertEqual(config.listeners[0].umask, 0o22)
        self.assertTrue(config.include_date_header)
        self.assertEqual(config.default_response_headers, [(b'x-phase1', b'enabled')])
        self.assertEqual(config.allowed_server_names, ('example.com', 'api.example.com'))
        self.assertTrue(config.logging.use_colors)

    def test_config_precedence_cli_over_env_over_env_file_over_file(self):
        parser = build_parser()
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / 'tigrcorn.json'
            env_path = Path(tmp) / '.env'
            config_path.write_text('{"app": {"target": "tests.fixtures_pkg.appmod:app"}, "logging": {"level": "debug"}}', encoding='utf-8')
            env_path.write_text('PHASE1_LOG_LEVEL=warning\n', encoding='utf-8')
            ns = parser.parse_args([
                '--config', str(config_path),
                '--env-file', str(env_path),
                '--env-prefix', 'PHASE1',
                '--log-level', 'error',
            ])
            with patch.dict(os.environ, {'PHASE1__LOGGING__LEVEL': 'info'}, clear=False):
                config = build_config_from_namespace(ns)
        self.assertEqual(config.logging.level, 'error')

    def test_yaml_module_and_object_config_sources_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            yaml_path = root / 'config.yaml'
            yaml_path.write_text('app:\n  target: tests.fixtures_pkg.appmod:app\nproxy:\n  server_names: [example.com]\n', encoding='utf-8')
            module_path = root / 'phase1_cfg.py'
            module_path.write_text(
                textwrap.dedent(
                    '''
                    CONFIG = {
                        "app": {"target": "tests.fixtures_pkg.appmod:app"},
                        "logging": {"level": "warning"},
                    }
                    OBJECT = {
                        "app": {"target": "tests.fixtures_pkg.appmod:app"},
                        "proxy": {"include_date_header": False},
                    }
                    '''
                ),
                encoding='utf-8',
            )
            with patch.object(sys, 'path', [tmp, *sys.path]):
                yaml_cfg = load_config_source(str(yaml_path))
                module_cfg = load_config_source('module:phase1_cfg')
                object_cfg = load_config_source('object:phase1_cfg:OBJECT')
        self.assertEqual(yaml_cfg['proxy']['server_names'], ['example.com'])
        self.assertEqual(module_cfg['logging']['level'], 'warning')
        self.assertEqual(object_cfg['proxy']['include_date_header'], False)

    def test_response_header_policy_and_websocket_handshake_include_phase1_headers(self):
        headers = apply_response_header_policy(
            [(b'content-type', b'text/plain')],
            server_header=b'tigrcorn',
            include_date_header=True,
            default_headers=['x-checkpoint: phase1'],
        )
        self.assertEqual(get_header(headers, b'x-checkpoint'), b'phase1')
        self.assertEqual(get_header(headers, b'server'), b'tigrcorn')
        self.assertIsNotNone(get_header(headers, b'date'))

        response = build_handshake_response(
            b'dGhlIHNhbXBsZSBub25jZQ==',
            subprotocol='chat',
            headers=[(b'x-extra', b'1')],
            server_header=b'tigrcorn',
            include_date_header=True,
            default_headers=[(b'x-checkpoint', b'phase1')],
        )
        self.assertIn(b'HTTP/1.1 101 Switching Protocols', response)
        self.assertIn(b'sec-websocket-accept: ' + websocket_accept_value(b'dGhlIHNhbXBsZSBub25jZQ=='), response)
        self.assertIn(b'x-checkpoint: phase1', response.lower())
        self.assertIn(b'date: ', response.lower())

    def test_authority_allowlist_supports_exact_and_wildcard(self):
        self.assertTrue(authority_allowed(b'example.com', ['example.com']))
        self.assertTrue(authority_allowed(b'api.example.com:443', ['*.example.com:443']))
        self.assertFalse(authority_allowed(b'example.net', ['*.example.com']))
        self.assertFalse(authority_allowed(None, ['example.com']))

    def test_static_files_app_serves_file_and_blocks_traversal(self):
        async def exercise() -> None:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / 'hello.txt').write_text('hello world', encoding='utf-8')
                app = StaticFilesApp(root)

                sent: list[dict] = []
                async def receive() -> dict:
                    return {'type': 'http.request', 'body': b'', 'more_body': False}
                async def send(message: dict) -> None:
                    sent.append(message)

                await app({'type': 'http', 'method': 'GET', 'path': '/hello.txt'}, receive, send)
                self.assertEqual(sent[0]['status'], 200)
                self.assertEqual(sent[1]['body'], b'hello world')

                sent.clear()
                await app({'type': 'http', 'method': 'GET', 'path': '/../secret.txt'}, receive, send)
                self.assertEqual(sent[0]['status'], 404)

                sent.clear()
                await app({'type': 'http', 'method': 'HEAD', 'path': '/hello.txt'}, receive, send)
                self.assertEqual(sent[0]['status'], 200)
                self.assertEqual(sent[1]['body'], b'')

        asyncio.run(exercise())


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
