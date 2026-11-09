from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import textwrap
from pathlib import Path
from unittest.mock import patch

from tigrcorn.cli import build_parser
from tigrcorn.config.files import load_config_source
from tigrcorn.config.load import build_config_from_namespace
from tigrcorn.protocols.websocket.handshake import (
    build_handshake_response,
    websocket_accept_value,
)
from tigrcorn.static import StaticFilesApp
from tigrcorn.utils.authority import authority_allowed
from tigrcorn.utils.headers import apply_response_header_policy, get_header


def test_parser_and_namespace_map_new_phase1_flags():
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
    assert config.app.env_file.endswith('.env.test')
    assert config.process.runtime == 'uvloop'
    assert config.process.worker_healthcheck_timeout == 9.5
    assert config.listeners[0].kind == 'unix'
    assert config.listeners[0].user == 1000
    assert config.listeners[0].group == 1001
    assert config.listeners[0].umask == 0o22
    assert config.include_date_header
    assert config.default_response_headers == [(b'x-phase1', b'enabled')]
    assert config.allowed_server_names == ('example.com', 'api.example.com')
    assert config.logging.use_colors


def test_config_precedence_cli_over_env_over_env_file_over_file():
    parser = build_parser()
    with tempfile.TemporaryDirectory() as tmp:
        config_path = Path(tmp) / 'tigrcorn.json'
        env_path = Path(tmp) / '.env'
        config_path.write_text(
            '{"app": {"target": "tests.fixtures_pkg.appmod:app"}, "logging": {"level": "debug"}}',
            encoding='utf-8',
        )
        env_path.write_text('PHASE1_LOG_LEVEL=warning\n', encoding='utf-8')
        ns = parser.parse_args(
            [
                '--config',
                str(config_path),
                '--env-file',
                str(env_path),
                '--env-prefix',
                'PHASE1',
                '--log-level',
                'error',
            ]
        )
        with patch.dict(os.environ, {'PHASE1__LOGGING__LEVEL': 'info'}, clear=False):
            config = build_config_from_namespace(ns)
    assert config.logging.level == 'error'


def test_yaml_module_and_object_config_sources_load():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        yaml_path = root / 'config.yaml'
        yaml_path.write_text(
            'app:\n  target: tests.fixtures_pkg.appmod:app\nproxy:\n  server_names: [example.com]\n',
            encoding='utf-8',
        )
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
    assert yaml_cfg['proxy']['server_names'] == ['example.com']
    assert module_cfg['logging']['level'] == 'warning'
    assert object_cfg['proxy']['include_date_header'] is False


def test_response_header_policy_and_websocket_handshake_include_phase1_headers():
    headers = apply_response_header_policy(
        [(b'content-type', b'text/plain')],
        server_header=b'tigrcorn',
        include_date_header=True,
        default_headers=['x-checkpoint: phase1'],
    )
    assert get_header(headers, b'x-checkpoint') == b'phase1'
    assert get_header(headers, b'server') == b'tigrcorn'
    assert get_header(headers, b'date') is not None

    response = build_handshake_response(
        b'dGhlIHNhbXBsZSBub25jZQ==',
        subprotocol='chat',
        headers=[(b'x-extra', b'1')],
        server_header=b'tigrcorn',
        include_date_header=True,
        default_headers=[(b'x-checkpoint', b'phase1')],
    )
    assert b'HTTP/1.1 101 Switching Protocols' in response
    assert (
        b'sec-websocket-accept: ' + websocket_accept_value(b'dGhlIHNhbXBsZSBub25jZQ==')
        in response
    )
    assert b'x-checkpoint: phase1' in response.lower()
    assert b'date: ' in response.lower()


def test_authority_allowlist_supports_exact_and_wildcard():
    assert authority_allowed(b'example.com', ['example.com'])
    assert authority_allowed(b'api.example.com:443', ['*.example.com:443'])
    assert not authority_allowed(b'example.net', ['*.example.com'])
    assert not authority_allowed(None, ['example.com'])


def test_static_files_app_serves_file_and_blocks_traversal():
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
            assert sent[0]['status'] == 200
            assert sent[1]['body'] == b'hello world'

            sent.clear()
            await app(
                {'type': 'http', 'method': 'GET', 'path': '/../secret.txt'},
                receive,
                send,
            )
            assert sent[0]['status'] == 404

            sent.clear()
            await app({'type': 'http', 'method': 'HEAD', 'path': '/hello.txt'}, receive, send)
            assert sent[0]['status'] == 200
            assert sent[1]['body'] == b''

    asyncio.run(exercise())
