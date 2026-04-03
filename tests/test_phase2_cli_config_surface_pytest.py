from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from tigrcorn.cli import build_parser
from tigrcorn.config.load import build_config_from_namespace


import pytest
class TestPhase2CLIConfigSurfaceTests:
    def test_parser_accepts_grouped_phase2_flags(self):
        parser = build_parser()
        ns = parser.parse_args(
            [
                'tests.fixtures_pkg.appmod:app',
                '--factory',
                '--app-dir', '.',
                '--reload',
                '--reload-dir', 'src',
                '--reload-include', '*.py',
                '--workers', '2',
                '--worker-class', 'process',
                '--pid', '/tmp/tigrcorn.pid',
                '--bind', '127.0.0.1:9000',
                '--quic-bind', '127.0.0.1:9443',
                '--transport', 'udp',
                '--reuse-port',
                '--backlog', '100',
                '--static-path-route', '/assets',
                '--static-path-mount', '/srv/assets',
                '--static-path-dir-to-file',
                '--static-path-index-file', 'index.html',
                '--static-path-expires', '3600',
                '--ssl-certfile', 'cert.pem',
                '--ssl-keyfile', 'key.pem',
                '--ssl-ca-certs', 'ca.pem',
                '--ssl-require-client-cert',
                '--ssl-alpn', 'h3',
                '--proxy-headers',
                '--forwarded-allow-ips', '127.0.0.1,10.0.0.1',
                '--root-path', '/svc',
                '--server-header', 'tigrcorn-test',
                '--log-level', 'debug',
                '--access-log',
                '--structured-log',
                '--metrics',
                '--metrics-bind', '127.0.0.1:9001',
                '--statsd-host', '127.0.0.1:8125',
                '--timeout-keep-alive', '6',
                '--read-timeout', '11',
                '--write-timeout', '12',
                '--timeout-graceful-shutdown', '13',
                '--limit-concurrency', '55',
                '--max-connections', '100',
                '--max-tasks', '200',
                '--max-streams', '10',
                '--max-body-size', '65536',
                '--max-header-size', '4096',
                '--websocket-max-message-size', '2048',
                '--websocket-ping-interval', '20',
                '--websocket-ping-timeout', '5',
                '--idle-timeout', '40',
                '--http', '3',
                '--protocol', 'http3',
                '--disable-h2c',
                '--websocket-compression', 'permessage-deflate',
                '--connect-policy', 'relay',
                '--trailer-policy', 'strict',
                '--content-coding-policy', 'allowlist',
                '--content-codings', 'gzip,deflate',
                '--quic-require-retry',
                '--quic-max-datagram-size', '1350',
                '--quic-idle-timeout', '50',
                '--quic-early-data-policy', 'deny',
            ]
        )
        assert ns.worker_class == 'process'
        assert ns.backlog == 100
        assert ns.static_path_route == '/assets'
        assert ns.static_path_mount == '/srv/assets'
        assert ns.static_path_dir_to_file == True
        assert ns.static_path_index_file == 'index.html'
        assert ns.static_path_expires == 3600
        assert ns.root_path == '/svc'
        assert ns.quic_bind == ['127.0.0.1:9443']
        assert ns.content_codings == ['gzip,deflate']
    def test_build_config_from_namespace_maps_nested_submodels(self):
        parser = build_parser()
        ns = parser.parse_args(
            [
                'tests.fixtures_pkg.appmod:app',
                '--transport', 'udp',
                '--protocol', 'http3',
                '--http', '3',
                '--ssl-certfile', 'cert.pem',
                '--ssl-keyfile', 'key.pem',
                '--ssl-ca-certs', 'ca.pem',
                '--ssl-require-client-cert',
                '--ssl-alpn', 'h3',
                '--max-body-size', '1024',
                '--max-header-size', '512',
                '--websocket-max-message-size', '4096',
                '--websocket-compression', 'permessage-deflate',
                '--quic-require-retry',
                '--quic-max-datagram-size', '1400',
                '--static-path-route', '/assets',
                '--static-path-mount', '/srv/assets',
                '--no-static-path-dir-to-file',
                '--static-path-index-file', 'home.html',
                '--static-path-expires', '90',
                '--connect-policy', 'allowlist',
                '--trailer-policy', 'drop',
                '--content-coding-policy', 'identity-only',
                '--content-codings', 'gzip',
                '--limit-concurrency', '3',
                '--max-streams', '2',
                '--server-header', 'demo',
            ]
        )
        config = build_config_from_namespace(ns)
        assert config.app.target == 'tests.fixtures_pkg.appmod:app'
        assert config.tls.certfile == 'cert.pem'
        assert config.tls.alpn_protocols == ['h3']
        assert config.http.max_body_size == 1024
        assert config.http.max_header_size == 512
        assert config.websocket.max_message_size == 4096
        assert config.websocket.compression == 'permessage-deflate'
        assert config.quic.max_datagram_size == 1400
        assert config.quic.require_retry == True
        assert config.static.route == '/assets'
        assert config.static.mount == '/srv/assets'
        assert config.static.dir_to_file == False
        assert config.static.index_file == 'home.html'
        assert config.static.expires == 90
        assert config.http.connect_policy == 'allowlist'
        assert config.http.trailer_policy == 'drop'
        assert config.http.content_coding_policy == 'identity-only'
        assert config.http.content_codings == ['gzip']
        assert config.scheduler.limit_concurrency == 3
        assert config.scheduler.max_streams == 2
        assert config.server_header_value == b'demo'
        assert config.listeners[0].kind == 'udp'
        assert config.listeners[0].protocols[:2] == ['quic', 'http3']
    def test_config_source_precedence_cli_over_env_over_file(self):
        parser = build_parser()
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / 'tigrcorn.json'
            config_path.write_text(json.dumps({
                'app': {'target': 'tests.fixtures_pkg.appmod:app'},
                'logging': {'level': 'debug'},
                'http': {'max_body_size': 99},
            }))
            ns = parser.parse_args([
                '--config', str(config_path),
                '--env-prefix', 'PHASE2TEST',
                '--log-level', 'info',
                '--max-body-size', '101',
            ])
            with patch.dict(os.environ, {
                'PHASE2TEST__LOGGING__LEVEL': 'warning',
                'PHASE2TEST__HTTP__MAX_BODY_SIZE': '100',
            }, clear=False):
                config = build_config_from_namespace(ns)
        assert config.logging.level == 'info'
        assert config.http.max_body_size == 101
    def test_env_prefix_is_respected(self):
        parser = build_parser()
        ns = parser.parse_args(['--env-prefix', 'PHASE2ALT'])
        with patch.dict(os.environ, {
            'PHASE2ALT__APP__TARGET': 'tests.fixtures_pkg.appmod:app',
            'PHASE2ALT__LOGGING__LEVEL': 'warning',
        }, clear=False):
            config = build_config_from_namespace(ns)
        assert config.app.target == 'tests.fixtures_pkg.appmod:app'
        assert config.logging.level == 'warning'
    def test_app_dir_round_trip(self):
        parser = build_parser()
        ns = parser.parse_args(['tests.fixtures_pkg.appmod:app', '--app-dir', '.'])
        config = build_config_from_namespace(ns)
        assert config.app.app_dir == '.'
    def test_cli_flag_surface_json_covers_public_parser_flags(self):
        parser = build_parser()
        public_flags: set[str] = set()
        for action in parser._actions:
            if isinstance(action, argparse._HelpAction):
                continue
            if action.help == argparse.SUPPRESS:
                continue
            for flag in action.option_strings:
                public_flags.add(flag)
        payload = json.loads(Path('docs/review/conformance/cli_flag_surface.json').read_text(encoding='utf-8'))
        documented_flags = {flag for entry in payload['flags'] for flag in entry['flags']}
        missing = sorted(public_flags - documented_flags)
        assert missing == []