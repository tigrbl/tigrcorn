from __future__ import annotations

import asyncio
import contextlib
import json
import socket
import tempfile
import threading
import time
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

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONFORMANCE = ROOT / "docs" / "review" / "conformance"


async def _noop_app(scope, receive, send):
    if scope["type"] == "lifespan":
        return
    await send({"type": "http.response.start", "status": 204, "headers": []})
    await send({"type": "http.response.body", "body": b"", "more_body": False})


class Test_CaptureHandler(BaseHTTPRequestHandler):
    requests: list[dict[str, object]] = []

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("content-length", "0"))
        body = self.rfile.read(length)
        self.__class__.requests.append(
            {
                "path": self.path,
                "headers": dict(self.headers.items()),
                "payload": json.loads(body.decode("utf-8")),
            }
        )
        self.send_response(200)
        self.send_header("content-length", "0")
        self.end_headers()

    def log_message(self, _format, *args):  # pragma: no cover
        return



def test_log_config_file_is_real_runtime_input_and_cli_flags_override_it():
    parser = build_parser()
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        profile_path = tmpdir / "logging.json"
        access_from_file = tmpdir / "access-from-file.log"
        error_from_file = tmpdir / "error-from-file.log"
        access_from_cli = tmpdir / "access-from-cli.log"
        error_from_cli = tmpdir / "error-from-cli.log"
        profile_path.write_text(
            json.dumps(
                {
                    "logging": {
                        "level": "error",
                        "structured": False,
                        "access_log_file": str(access_from_file),
                        "error_log_file": str(error_from_file),
                        "access_log_format": "FILE {peer}",
                        "stream": False,
                    }
                }
            ),
            encoding="utf-8",
        )

        ns = parser.parse_args(
            [
                "tests.fixtures_pkg.appmod:app",
                "--log-config",
                str(profile_path),
                "--log-level",
                "debug",
                "--structured-log",
                "--access-log-file",
                str(access_from_cli),
                "--error-log-file",
                str(error_from_cli),
            ]
        )
        config = build_config_from_namespace(ns)
        resolved = resolve_logging_config(config.log_level, config=config.logging)
        assert resolved.level == "debug"
        assert resolved.structured
        assert resolved.access_log_file == str(access_from_cli)
        assert resolved.error_log_file == str(error_from_cli)
        logger = configure_logging(config.log_level, config=config.logging)
        logger.debug("phase9f2-log-config-debug")
        for handler in logger.handlers:
            handler.flush()
        assert access_from_cli.exists()
        assert error_from_cli.exists()
        assert not (access_from_file.exists())
        payload = access_from_cli.read_text(encoding="utf-8")
        assert "phase9f2-log-config-debug" in payload
        assert '"message": "phase9f2-log-config-debug"' in payload

def test_log_config_file_wins_when_no_explicit_cli_logging_overrides_exist():
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        profile_path = tmpdir / "logging.json"
        error_path = tmpdir / "errors.log"
        profile_path.write_text(
            json.dumps(
                {
                    "logging": {
                        "level": "error",
                        "structured": True,
                        "error_log_file": str(error_path),
                        "stream": False,
                    }
                }
            ),
            encoding="utf-8",
        )
        config = build_config(config={"logging": {"log_config": str(profile_path)}})
        resolved = resolve_logging_config(config.log_level, config=config.logging)
        assert resolved.level == "error"
        assert resolved.structured
        logger = configure_logging(config.log_level, config=config.logging)
        logger.debug("debug-not-emitted")
        logger.error("error-emitted")
        for handler in logger.handlers:
            handler.flush()
        data = error_path.read_text(encoding="utf-8")
        assert "error-emitted" in data
        assert "debug-not-emitted" not in data

def test_invalid_log_config_fails_fast():
    parser = build_parser()
    with tempfile.TemporaryDirectory() as tmp:
        bad_path = Path(tmp) / "bad.json"
        bad_path.write_text(
            json.dumps({"logging": {"unsupported": True}}), encoding="utf-8"
        )
        ns = parser.parse_args(
            ["tests.fixtures_pkg.appmod:app", "--log-config", str(bad_path)]
        )
        with pytest.raises(ConfigError):
            build_config_from_namespace(ns)

async def test_statsd_exporter_emits_real_udp_traffic_during_server_lifecycle():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))
    sock.setblocking(False)
    host, port = sock.getsockname()
    config = build_config(config={"metrics": {"statsd_host": f"{host}:{port}"}})
    server = TigrCornServer(_noop_app, config)
    try:
        await server.start()
        data, _addr = await asyncio.wait_for(
            asyncio.get_running_loop().sock_recvfrom(sock, 65535), 2.0
        )
        payload = data.decode("utf-8")
        assert "tigrcorn.connections_opened" in payload
        assert "tigrcorn.requests_served" in payload
        assert server._statsd_exporter.sent_packets >= 1
    finally:
        await server.close()
        sock.close()

async def test_otel_exporter_posts_metrics_and_lifecycle_spans():
    _CaptureHandler.requests = []
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _CaptureHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    endpoint = f"http://127.0.0.1:{httpd.server_address[1]}/v1/telemetry"
    config = build_config(config={"metrics": {"otel_endpoint": endpoint}})
    server = TigrCornServer(_noop_app, config)
    try:
        await server.start()
        await asyncio.sleep(0.25)
    finally:
        await server.close()
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=1.0)
    assert len(_CaptureHandler.requests) >= 2
    span_names = []
    metrics_seen = False
    for item in _CaptureHandler.requests:
        payload = item["payload"]
        assert "resourceMetrics" in payload
        assert "resourceSpans" in payload
        if payload["resourceMetrics"][0]["scopeMetrics"][0]["metrics"]:
            metrics_seen = True
        for span_payload in payload["resourceSpans"][0]["scopeSpans"][0]["spans"]:
            span_names.append(span_payload["name"])
    assert metrics_seen
    assert "server.start" in span_names
    assert "server.shutdown" in span_names

async def test_exporter_failures_are_bounded_and_do_not_abort_server_startup():
    config = build_config(
        config={
            "metrics": {
                "statsd_host": "127.0.0.1:8125",
                "otel_endpoint": "http://127.0.0.1:9/v1/telemetry",
            }
        }
    )
    with (
        patch.object(
            StatsdExporter, "_ensure_socket", side_effect=OSError("statsd boom")
        ),
        patch.object(OtelExporter, "_post_json", side_effect=URLError("otel boom")),
    ):
        server = TigrCornServer(_noop_app, config)
        await server.start()
        assert server._statsd_exporter is not None
        assert server._otel_exporter is not None
        assert server._statsd_exporter.send_failures >= 1
        assert server._otel_exporter.send_failures >= 1
        await server.close()

def test_phase9f2_status_snapshot_matches_current_flag_surface_state():
    payload = json.loads(
        (CONFORMANCE / "phase9f2_logging_exporter.current.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["phase"] == "9F2"
    for flag in ["--log-config", "--statsd-host", "--otel-endpoint"]:
        assert (
            flag not in payload["current_state"]["remaining_flag_runtime_blockers"]
        )
    failures = "\n".join(evaluate_promotion_target(ROOT).flag_surface.failures)
    assert "--log-config" not in failures
    assert "--statsd-host" not in failures
    assert "--otel-endpoint" not in failures
    assert "--limit-concurrency" not in failures
    assert evaluate_promotion_target(ROOT).flag_surface.passed
