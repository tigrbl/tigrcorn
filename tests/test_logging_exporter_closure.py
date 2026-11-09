from __future__ import annotations

import asyncio
import contextlib
import json
import socket
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import URLError

from tigrcorn.cli import build_parser
from tigrcorn.compat.release_gates import evaluate_promotion_target
from tigrcorn.config.load import build_config, build_config_from_namespace
from tigrcorn.errors import ConfigError
from tigrcorn.observability.logging import configure_logging, resolve_logging_config
from tigrcorn.observability.metrics import StatsdExporter
from tigrcorn.observability.tracing import OtelExporter
from tigrcorn.server.runner import TigrCornServer

ROOT = Path(__file__).resolve().parents[1]


@contextlib.contextmanager
def _workspace_tempdir():
    with tempfile.TemporaryDirectory(dir='.') as tmp:
        yield Path(tmp).resolve()


def _close_logger_handlers(logger) -> None:
    for handler in list(logger.handlers):
        with contextlib.suppress(Exception):
            handler.flush()
        with contextlib.suppress(Exception):
            handler.close()
        with contextlib.suppress(Exception):
            logger.removeHandler(handler)


async def _noop_app(scope, receive, send):
    if scope['type'] == 'lifespan':
        return
    await send({'type': 'http.response.start', 'status': 204, 'headers': []})
    await send({'type': 'http.response.body', 'body': b'', 'more_body': False})


def _recvfrom_blocking(sock: socket.socket, size: int) -> tuple[bytes, tuple[str, int]]:
    sock.setblocking(True)
    try:
        return sock.recvfrom(size)
    finally:
        sock.setblocking(False)


async def _loop_sock_recvfrom(sock: socket.socket, size: int) -> tuple[bytes, tuple[str, int]]:
    loop = asyncio.get_running_loop()
    if hasattr(loop, 'sock_recvfrom'):
        return await loop.sock_recvfrom(sock, size)
    return await loop.run_in_executor(None, _recvfrom_blocking, sock, size)


class _CaptureHandler(BaseHTTPRequestHandler):
    requests: list[dict[str, object]] = []

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get('content-length', '0'))
        body = self.rfile.read(length)
        self.__class__.requests.append(
            {
                'path': self.path,
                'headers': dict(self.headers.items()),
                'payload': json.loads(body.decode('utf-8')),
            }
        )
        self.send_response(200)
        self.send_header('content-length', '0')
        self.end_headers()

    def log_message(self, _format, *args):  # pragma: no cover
        return


class LoggingExporterClosureTests(unittest.IsolatedAsyncioTestCase):
    def test_log_config_file_is_real_runtime_input_and_cli_flags_override_it(self):
        parser = build_parser()
        with _workspace_tempdir() as tmpdir:
            profile_path = tmpdir / 'logging.json'
            access_from_file = tmpdir / 'access-from-file.log'
            error_from_file = tmpdir / 'error-from-file.log'
            access_from_cli = tmpdir / 'access-from-cli.log'
            error_from_cli = tmpdir / 'error-from-cli.log'
            profile_path.write_text(
                json.dumps(
                    {
                        'logging': {
                            'level': 'error',
                            'structured': False,
                            'access_log_file': str(access_from_file),
                            'error_log_file': str(error_from_file),
                            'access_log_format': 'FILE {peer}',
                            'stream': False,
                        }
                    }
                ),
                encoding='utf-8',
            )

            ns = parser.parse_args(
                [
                    'tests.fixtures_pkg.appmod:app',
                    '--log-config',
                    str(profile_path),
                    '--log-level',
                    'debug',
                    '--structured-log',
                    '--access-log-file',
                    str(access_from_cli),
                    '--error-log-file',
                    str(error_from_cli),
                ]
            )
            config = build_config_from_namespace(ns)
            resolved = resolve_logging_config(config.log_level, config=config.logging)
            self.assertEqual(resolved.level, 'debug')
            self.assertTrue(resolved.structured)
            self.assertEqual(resolved.access_log_file, str(access_from_cli))
            self.assertEqual(resolved.error_log_file, str(error_from_cli))

            logger = configure_logging(config.log_level, config=config.logging)
            try:
                logger.debug('logging-exporter-config-debug')
                for handler in logger.handlers:
                    handler.flush()
                self.assertTrue(access_from_cli.exists())
                self.assertTrue(error_from_cli.exists())
                self.assertFalse(access_from_file.exists())
                payload = access_from_cli.read_text(encoding='utf-8')
                self.assertIn('logging-exporter-config-debug', payload)
                self.assertIn('"message": "logging-exporter-config-debug"', payload)
            finally:
                _close_logger_handlers(logger)

    def test_log_config_file_wins_when_no_explicit_cli_logging_overrides_exist(self):
        with _workspace_tempdir() as tmpdir:
            profile_path = tmpdir / 'logging.json'
            error_path = tmpdir / 'errors.log'
            profile_path.write_text(
                json.dumps(
                    {
                        'logging': {
                            'level': 'error',
                            'structured': True,
                            'error_log_file': str(error_path),
                            'stream': False,
                        }
                    }
                ),
                encoding='utf-8',
            )
            config = build_config(config={'logging': {'log_config': str(profile_path)}})
            resolved = resolve_logging_config(config.log_level, config=config.logging)
            self.assertEqual(resolved.level, 'error')
            self.assertTrue(resolved.structured)
            logger = configure_logging(config.log_level, config=config.logging)
            try:
                logger.debug('debug-not-emitted')
                logger.error('error-emitted')
                for handler in logger.handlers:
                    handler.flush()
                data = error_path.read_text(encoding='utf-8')
                self.assertIn('error-emitted', data)
                self.assertNotIn('debug-not-emitted', data)
            finally:
                _close_logger_handlers(logger)

    def test_invalid_log_config_fails_fast(self):
        parser = build_parser()
        with _workspace_tempdir() as tmpdir:
            bad_path = tmpdir / 'bad.json'
            bad_path.write_text(json.dumps({'logging': {'unsupported': True}}), encoding='utf-8')
            ns = parser.parse_args(['tests.fixtures_pkg.appmod:app', '--log-config', str(bad_path)])
            with self.assertRaises(ConfigError):
                build_config_from_namespace(ns)

    def test_pep391_dict_logging_config_drives_runtime_handlers(self):
        parser = build_parser()
        with _workspace_tempdir() as tmpdir:
            output_path = tmpdir / 'pep391.log'
            profile_path = tmpdir / 'pep391.json'
            profile_path.write_text(
                json.dumps(
                    {
                        'version': 1,
                        'disable_existing_loggers': False,
                        'formatters': {
                            'plain': {
                                'format': 'pep391:%(levelname)s:%(name)s:%(message)s',
                            }
                        },
                        'handlers': {
                            'file': {
                                'class': 'logging.FileHandler',
                                'filename': str(output_path),
                                'encoding': 'utf-8',
                                'formatter': 'plain',
                            }
                        },
                        'loggers': {
                            'tigrcorn': {
                                'handlers': ['file'],
                                'level': 'DEBUG',
                                'propagate': False,
                            }
                        },
                    }
                ),
                encoding='utf-8',
            )
            ns = parser.parse_args(['tests.fixtures_pkg.appmod:app', '--log-config', str(profile_path)])
            config = build_config_from_namespace(ns)
            logger = configure_logging(config.log_level, config=config.logging)
            try:
                logger.debug('dict-config-event')
                for handler in logger.handlers:
                    handler.flush()
                self.assertIn(
                    'pep391:DEBUG:tigrcorn:dict-config-event',
                    output_path.read_text(encoding='utf-8'),
                )
            finally:
                _close_logger_handlers(logger)

    def test_rfc5424_log_config_profile_formats_runtime_records(self):
        with _workspace_tempdir() as tmpdir:
            profile_path = tmpdir / 'rfc5424.json'
            output_path = tmpdir / 'syslog.log'
            profile_path.write_text(
                json.dumps(
                    {
                        'logging': {
                            'level': 'info',
                            'format': 'rfc5424',
                            'error_log_file': str(output_path),
                            'stream': False,
                            'syslog_app_name': 'tigrcorn-test',
                            'syslog_procid': 'worker-1',
                            'syslog_msgid': 'ACCESS',
                        }
                    }
                ),
                encoding='utf-8',
            )
            config = build_config(config={'logging': {'log_config': str(profile_path)}})
            logger = configure_logging(config.log_level, config=config.logging)
            try:
                logger.info(
                    'request-complete',
                    extra={
                        'event': 'access.http',
                        'method': 'GET',
                        'path': '/health',
                        'status': 204,
                    },
                )
                for handler in logger.handlers:
                    handler.flush()
                line = output_path.read_text(encoding='utf-8').strip()
                self.assertTrue(line.startswith('<14>1 '))
                self.assertIn(' tigrcorn-test worker-1 ACCESS ', line)
                self.assertIn('[tigrcorn@32473 ', line)
                self.assertIn('event="access.http"', line)
                self.assertIn('status="204"', line)
                self.assertTrue(line.endswith(' request-complete'))
            finally:
                _close_logger_handlers(logger)

    async def test_statsd_exporter_emits_real_udp_traffic_during_server_lifecycle(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(('127.0.0.1', 0))
        sock.setblocking(False)
        host, port = sock.getsockname()
        config = build_config(port=0, config={'metrics': {'statsd_host': f'{host}:{port}'}})
        server = TigrCornServer(_noop_app, config)
        try:
            await server.start()
            data, _addr = await asyncio.wait_for(_loop_sock_recvfrom(sock, 65535), 2.0)
            payload = data.decode('utf-8')
            self.assertIn('tigrcorn.connections_opened', payload)
            self.assertIn('tigrcorn.requests_served', payload)
            self.assertGreaterEqual(server._statsd_exporter.sent_packets, 1)
        finally:
            await server.close()
            sock.close()

    async def test_otel_exporter_posts_metrics_and_lifecycle_spans(self):
        _CaptureHandler.requests = []
        httpd = ThreadingHTTPServer(('127.0.0.1', 0), _CaptureHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        endpoint = f'http://127.0.0.1:{httpd.server_address[1]}/v1/telemetry'
        config = build_config(port=0, config={'metrics': {'otel_endpoint': endpoint}})
        server = TigrCornServer(_noop_app, config)
        try:
            await server.start()
            await asyncio.sleep(0.25)
        finally:
            await server.close()
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=1.0)
        self.assertGreaterEqual(len(_CaptureHandler.requests), 2)
        span_names = []
        metrics_seen = False
        for item in _CaptureHandler.requests:
            payload = item['payload']
            self.assertIn('resourceMetrics', payload)
            self.assertIn('resourceSpans', payload)
            if payload['resourceMetrics'][0]['scopeMetrics'][0]['metrics']:
                metrics_seen = True
            for span_payload in payload['resourceSpans'][0]['scopeSpans'][0]['spans']:
                span_names.append(span_payload['name'])
        self.assertTrue(metrics_seen)
        self.assertIn('server.start', span_names)
        self.assertIn('server.shutdown', span_names)

    async def test_exporter_failures_are_bounded_and_do_not_abort_server_startup(self):
        config = build_config(
            port=0,
            config={
                'metrics': {
                    'statsd_host': '127.0.0.1:8125',
                    'otel_endpoint': 'http://127.0.0.1:9/v1/telemetry',
                }
            }
        )
        with (
            patch.object(StatsdExporter, '_ensure_socket', side_effect=OSError('statsd boom')),
            patch.object(OtelExporter, '_post_json', side_effect=URLError('otel boom')),
        ):
            server = TigrCornServer(_noop_app, config)
            await server.start()
            self.assertIsNotNone(server._statsd_exporter)
            self.assertIsNotNone(server._otel_exporter)
            self.assertGreaterEqual(server._statsd_exporter.send_failures, 1)
            self.assertGreaterEqual(server._otel_exporter.send_failures, 1)
            await server.close()

    def test_status_snapshot_matches_current_flag_surface_state(self):
        for flag in ['--log-config', '--statsd-host', '--otel-endpoint']:
            self.assertNotIn(flag, evaluate_promotion_target(ROOT).flag_surface.failures)
        failures = '\n'.join(evaluate_promotion_target(ROOT).flag_surface.failures)
        self.assertNotIn('--log-config', failures)
        self.assertNotIn('--statsd-host', failures)
        self.assertNotIn('--otel-endpoint', failures)
        self.assertNotIn('--limit-concurrency', failures)
        self.assertTrue(evaluate_promotion_target(ROOT).flag_surface.passed)


if __name__ == '__main__':
    unittest.main()
