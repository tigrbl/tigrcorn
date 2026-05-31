from __future__ import annotations

import json
import logging
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from tigrcorn.asgi.scopes.http import build_http_scope
from tigrcorn.asgi.scopes.websocket import build_websocket_scope
from tigrcorn.cli import build_parser
from tigrcorn.config.load import build_config_from_namespace
from tigrcorn.config.model import ProxyConfig, ServerConfig
from tigrcorn.config.validate import validate_config
from tigrcorn.observability.logging import AccessLogger, configure_logging
from tigrcorn.observability.metrics import Metrics
from tigrcorn.protocols.http1.parser import ParsedRequest
from tigrcorn.server.reloader import PollingReloader
from tigrcorn.server.supervisor import ServerSupervisor
from tigrcorn.workers.local import LocalWorker
from tigrcorn.workers.process import ProcessWorker
from tigrcorn.workers.supervisor import WorkerSupervisor
from tigrcorn.errors import ConfigError


def _sleep_worker(seconds: float = 10.0) -> None:
    time.sleep(seconds)


def _noop_worker(_payload) -> None:
    return None


class Phase4OperatorSurfaceTests(unittest.TestCase):
    def test_validate_rejects_reload_with_multiple_workers(self):
        parser = build_parser()
        ns = parser.parse_args(['tests.fixtures_pkg.appmod:app', '--reload', '--workers', '2'])
        with self.assertRaises(ConfigError):
            build_config_from_namespace(ns)

    def test_proxy_scope_building_applies_forwarded_headers(self):
        request = ParsedRequest(
            method='GET',
            target='/svc/hello',
            path='/svc/hello',
            raw_path=b'/svc/hello',
            query_string=b'',
            http_version='1.1',
            headers=[
                (b'x-forwarded-for', b'203.0.113.8'),
                (b'x-forwarded-proto', b'https'),
                (b'x-forwarded-host', b'example.com'),
                (b'x-forwarded-prefix', b'/svc'),
            ],
            body=b'',
            keep_alive=True,
            expect_continue=False,
            websocket_upgrade=False,
        )
        proxy = ProxyConfig(proxy_headers=True, forwarded_allow_ips=['127.0.0.1'])
        scope = build_http_scope(
            request,
            client=('127.0.0.1', 50000),
            server=('127.0.0.1', 8000),
            scheme='http',
            root_path='',
            proxy=proxy,
        )
        self.assertEqual(scope['client'], ('203.0.113.8', 50000))
        self.assertEqual(scope['scheme'], 'https')
        self.assertEqual(scope['server'], ('example.com', 8000))
        self.assertEqual(scope['root_path'], '/svc')
        self.assertEqual(scope['path'], '/hello')

    def test_websocket_scope_inherits_proxy_normalization(self):
        request = ParsedRequest(
            method='GET',
            target='/mount/ws',
            path='/mount/ws',
            raw_path=b'/mount/ws',
            query_string=b'',
            http_version='1.1',
            headers=[
                (b'forwarded', b'for=198.51.100.10;proto=wss;host=example.net'),
                (b'x-forwarded-prefix', b'/mount'),
                (b'sec-websocket-protocol', b'chat, superchat'),
            ],
            body=b'',
            keep_alive=True,
            expect_continue=False,
            websocket_upgrade=True,
        )
        proxy = ProxyConfig(proxy_headers=True, forwarded_allow_ips=['127.0.0.1'])
        scope = build_websocket_scope(
            request,
            client=('127.0.0.1', 50001),
            server=('127.0.0.1', 8000),
            scheme='ws',
            root_path='',
            proxy=proxy,
        )
        self.assertEqual(scope['client'], ('198.51.100.10', 50001))
        self.assertEqual(scope['scheme'], 'wss')
        self.assertEqual(scope['server'], ('example.net', 8000))
        self.assertEqual(scope['root_path'], '/mount')
        self.assertEqual(scope['path'], '/ws')
        self.assertEqual(scope['subprotocols'], ['chat', 'superchat'])

    def test_metrics_snapshot_and_exporters(self):
        metrics = Metrics()
        metrics.connection_opened()
        metrics.requests_served = 2
        metrics.websocket_opened()
        snapshot = metrics.snapshot()
        self.assertEqual(snapshot['connections_opened'], 1)
        self.assertEqual(snapshot['active_websocket_connections'], 1)
        self.assertIn('tigrcorn_requests_served', metrics.render_prometheus())
        self.assertIn('tigrcorn.requests_served', metrics.render_statsd())

    def test_configure_logging_supports_structured_and_file_handlers(self):
        with tempfile.TemporaryDirectory() as tmp:
            class LoggingCfg:
                level = 'info'
                structured = True
                access_log_file = str(Path(tmp) / 'access.log')
                error_log_file = str(Path(tmp) / 'error.log')
            logger = configure_logging('info', config=LoggingCfg())
            access = AccessLogger(logger, enabled=True)
            access.log_http(('127.0.0.1', 1), 'GET', '/', 200, 'HTTP/1.1')
            for handler in logger.handlers:
                handler.flush()
            self.assertTrue(Path(LoggingCfg.access_log_file).exists())
            payload = Path(LoggingCfg.access_log_file).read_text(encoding='utf-8')
            self.assertIn('"event": "access.http"', payload)

    def test_local_and_process_workers_expose_health(self):
        local = LocalWorker()
        local.start()
        self.assertTrue(local.health()['alive'])
        local.stop()
        worker = ProcessWorker(name='phase4-test-worker')
        worker.start(_sleep_worker, 10.0)
        try:
            self.assertTrue(worker.is_alive())
            self.assertIsNotNone(worker.health()['pid'])
        finally:
            worker.stop(timeout=0.5)

    def test_worker_supervisor_can_replace_local_worker(self):
        sup = WorkerSupervisor()
        first = LocalWorker(name='a')
        second = LocalWorker(name='b')
        sup.add(first)
        sup.start_all()
        self.assertTrue(first.running)
        sup.replace(0, second)
        self.assertTrue(second.running)
        self.assertFalse(first.running)
        sup.stop_all()
        self.assertFalse(second.running)

    def test_polling_reloader_detects_snapshot_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'app.py'
            source.write_text('x = 1\n', encoding='utf-8')
            parser = build_parser()
            ns = parser.parse_args(['tests.fixtures_pkg.appmod:app', '--reload', '--reload-dir', tmp])
            config = build_config_from_namespace(ns)
            reloader = PollingReloader(['tests.fixtures_pkg.appmod:app'], config=config, interval=0.01)
            snap1 = reloader.snapshot()
            time.sleep(0.02)
            source.write_text('x = 2\n', encoding='utf-8')
            snap2 = reloader.snapshot()
            self.assertNotEqual(snap1, snap2)

    def test_server_supervisor_restarts_dead_workers(self):
        parser = build_parser()
        with tempfile.TemporaryDirectory() as tmp:
            pidfile = str(Path(tmp) / 'tigrcorn.pid')
            ns = parser.parse_args(['tests.fixtures_pkg.appmod:app', '--workers', '1', '--pid', pidfile, '--port', '0'])
            config = build_config_from_namespace(ns)
            with patch('tigrcorn.server.supervisor.run_worker_from_config_payload', _noop_worker):
                supervisor = ServerSupervisor(app_target='tests.fixtures_pkg.appmod:app', config=config)
                supervisor.start()
                try:
                    self.assertTrue(Path(pidfile).exists())
                    time.sleep(0.1)
                    restarted = supervisor.poll_workers_once()
                    self.assertIsInstance(restarted, list)
                    self.assertEqual(len(supervisor.workers.workers), 1)
                finally:
                    supervisor.stop()
            self.assertFalse(Path(pidfile).exists())

    def test_cli_parser_still_accepts_operator_surface_flags(self):
        parser = build_parser()
        ns = parser.parse_args([
            'tests.fixtures_pkg.appmod:app',
            '--reload',
            '--reload-dir', 'src',
            '--workers', '1',
            '--pid', '/tmp/tigrcorn.pid',
            '--bind', '127.0.0.1:0',
            '--fd', '3',
            '--proxy-headers',
            '--forwarded-allow-ips', '127.0.0.1',
            '--root-path', '/svc',
            '--access-log-file', '/tmp/access.log',
            '--error-log-file', '/tmp/error.log',
            '--structured-log',
            '--metrics',
            '--metrics-bind', '127.0.0.1:9001',
            '--timeout-keep-alive', '7',
            '--read-timeout', '9',
            '--write-timeout', '10',
            '--timeout-graceful-shutdown', '11',
            '--limit-concurrency', '5',
            '--max-connections', '10',
            '--max-tasks', '20',
            '--max-streams', '3',
            '--max-header-size', '4096',
            '--websocket-max-message-size', '8192',
            '--idle-timeout', '15',
            '--quic-max-datagram-size', '1350',
            '--quic-idle-timeout', '30',
        ])
        self.assertEqual(ns.metrics_bind, '127.0.0.1:9001')
        self.assertEqual(ns.max_connections, 10)
        self.assertEqual(ns.max_streams, 3)
