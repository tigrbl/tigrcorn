from __future__ import annotations

import argparse
import asyncio
import os
import sys

from tigrcorn.api import serve_import_string
from tigrcorn.config.load import build_config_from_namespace
from tigrcorn.server.reloader import PollingReloader
from tigrcorn.server.supervisor import ServerSupervisor


def _add_flag_pair(group: argparse._ArgumentGroup, positive: str, negative: str, *, dest: str, help_text: str) -> None:
    group.add_argument(positive, action='store_true', dest=dest, default=None, help=help_text)
    group.add_argument(negative, action='store_false', dest=dest, default=None, help=f"Disable {help_text.lower()}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tigrcorn", description="ASGI3-compatible transport server")
    parser.add_argument("app", nargs="?", help="Application import string in module:attr form")

    app_group = parser.add_argument_group("App / process / development")
    app_group.add_argument("--factory", action="store_true", default=None, help="Treat APP as an application factory")
    app_group.add_argument("--app-dir", dest="app_dir", default=None, help="Add a directory to sys.path before loading the app")
    app_group.add_argument("--reload", action="store_true", default=None, help="Enable development autoreload")
    app_group.add_argument("--reload-dir", action="append", default=None, help="Directory to watch for reload")
    app_group.add_argument("--reload-include", action="append", default=None, help="Glob to include in reload watch set")
    app_group.add_argument("--reload-exclude", action="append", default=None, help="Glob to exclude from reload watch set")
    app_group.add_argument("--workers", type=int, default=None, help="Worker process count")
    app_group.add_argument("--worker-class", default=None, help="Worker/runtime implementation class")
    app_group.add_argument("--pid", default=None, help="PID file path")
    app_group.add_argument("--config", default=None, help="Config file path (.json, .toml, .py)")
    app_group.add_argument("--env-prefix", default=None, help="Environment variable prefix for config loading")
    app_group.add_argument("--lifespan", choices=["auto", "on", "off"], default=None)
    app_group.add_argument("--limit-max-requests", type=int, default=None, dest="limit_max_requests")
    app_group.add_argument("--max-requests-jitter", type=int, default=None)

    bind_group = parser.add_argument_group("Listener / binding")
    bind_group.add_argument("--bind", action="append", default=None, help="Bind listener as host:port")
    bind_group.add_argument("--host", default=None, help="Bind host for TCP/UDP listeners")
    bind_group.add_argument("--port", default=None, type=int, help="Bind port for TCP/UDP listeners")
    bind_group.add_argument("--uds", default=None, help="Bind Unix domain socket or pipe path")
    bind_group.add_argument("--fd", action="append", default=None, help="Use an inherited file descriptor listener")
    bind_group.add_argument("--endpoint", action="append", default=None, help="Endpoint / raw listener description")
    bind_group.add_argument("--insecure-bind", action="append", default=None, help="Additional insecure bind alongside TLS listener(s)")
    bind_group.add_argument("--quic-bind", action="append", default=None, help="Additional UDP/QUIC bind")
    bind_group.add_argument("--transport", choices=["tcp", "udp", "unix", "pipe", "inproc"], default=None)
    bind_group.add_argument("--reuse-port", action="store_true", default=None)
    bind_group.add_argument("--reuse-address", action="store_true", default=None)
    bind_group.add_argument("--backlog", type=int, default=None)

    tls_group = parser.add_argument_group("TLS / security")
    tls_group.add_argument("--ssl-certfile", default=None, help="Certificate for TLS on TCP/Unix or QUIC-TLS on UDP")
    tls_group.add_argument("--ssl-keyfile", default=None, help="Private key for TLS on TCP/Unix or QUIC-TLS on UDP")
    tls_group.add_argument("--ssl-ca-certs", default=None, help="Trusted CA bundle for client-certificate verification")
    tls_group.add_argument("--ssl-require-client-cert", action="store_true", default=None, help="Require peer client certificates")
    tls_group.add_argument("--ssl-ciphers", default=None)
    tls_group.add_argument("--ssl-alpn", action="append", default=None, help="ALPN protocol(s); repeat or use comma-separated values")
    tls_group.add_argument("--ssl-ocsp-mode", choices=["off", "soft-fail", "require"], default=None)
    tls_group.add_argument("--ssl-ocsp-soft-fail", action="store_true", default=None)
    tls_group.add_argument("--ssl-ocsp-cache-size", type=int, default=None)
    tls_group.add_argument("--ssl-ocsp-max-age", type=float, default=None)
    tls_group.add_argument("--ssl-crl-mode", choices=["off", "soft-fail", "require"], default=None)
    tls_group.add_argument("--ssl-revocation-fetch", choices=["off", "on"], default=None)
    tls_group.add_argument("--proxy-headers", action="store_true", default=None)
    tls_group.add_argument("--forwarded-allow-ips", action="append", default=None, help="Trusted forwarded-header peers; repeat or use comma-separated values")
    tls_group.add_argument("--root-path", default=None, help="ASGI root_path mount prefix")
    tls_group.add_argument("--server-header", nargs="?", const="tigrcorn", default=None, help="Enable or override the Server header value")
    tls_group.add_argument("--no-server-header", action="store_true", default=False, help="Disable the Server header")

    log_group = parser.add_argument_group("Logging / observability")
    log_group.add_argument("--log-level", default=None)
    _add_flag_pair(log_group, "--access-log", "--no-access-log", dest="access_log", help_text="Access logging")
    log_group.add_argument("--access-log-file", default=None)
    log_group.add_argument("--access-log-format", default=None)
    log_group.add_argument("--error-log-file", default=None)
    log_group.add_argument("--log-config", default=None)
    log_group.add_argument("--structured-log", action="store_true", default=None)
    log_group.add_argument("--metrics", action="store_true", default=None)
    log_group.add_argument("--metrics-bind", default=None)
    log_group.add_argument("--statsd-host", default=None)
    log_group.add_argument("--otel-endpoint", default=None)

    limit_group = parser.add_argument_group("Resource / timeouts / concurrency")
    limit_group.add_argument("--timeout-keep-alive", type=float, default=None)
    limit_group.add_argument("--read-timeout", type=float, default=None)
    limit_group.add_argument("--write-timeout", type=float, default=None)
    limit_group.add_argument("--timeout-graceful-shutdown", type=float, default=None)
    limit_group.add_argument("--limit-concurrency", type=int, default=None)
    limit_group.add_argument("--max-connections", type=int, default=None)
    limit_group.add_argument("--max-tasks", type=int, default=None)
    limit_group.add_argument("--max-streams", type=int, default=None)
    limit_group.add_argument("--max-body-size", type=int, default=None)
    limit_group.add_argument("--max-header-size", type=int, default=None)
    limit_group.add_argument("--websocket-max-message-size", type=int, default=None)
    limit_group.add_argument("--websocket-ping-interval", type=float, default=None)
    limit_group.add_argument("--websocket-ping-timeout", type=float, default=None)
    limit_group.add_argument("--idle-timeout", type=float, default=None)

    protocol_group = parser.add_argument_group("Protocol / transport")
    protocol_group.add_argument("--http", dest="http_versions", action="append", choices=["1.1", "2", "3"], default=None, help="Enable an HTTP version")
    protocol_group.add_argument("--protocol", dest="protocols", action="append", choices=["http1", "http2", "http3", "quic", "websocket", "rawframed", "custom"], default=None, help="Enable a listener protocol")
    protocol_group.add_argument("--disable-websocket", action="store_true", default=None)
    protocol_group.add_argument("--disable-h2c", action="store_true", default=None)
    protocol_group.add_argument("--websocket-compression", choices=["off", "permessage-deflate"], default=None)
    protocol_group.add_argument("--connect-policy", choices=["relay", "deny", "allowlist"], default=None)
    protocol_group.add_argument("--connect-allow", action="append", default=None, help="Repeat or use comma-separated host:port, host, or CIDR entries")
    protocol_group.add_argument("--trailer-policy", choices=["pass", "drop", "strict"], default=None)
    protocol_group.add_argument("--content-coding-policy", choices=["allowlist", "identity-only", "strict"], default=None)
    protocol_group.add_argument("--content-codings", action="append", default=None, help="Repeat or use comma-separated values")
    protocol_group.add_argument("--quic-require-retry", action="store_true", default=None, help="Require a QUIC Retry before completing the initial handshake")
    protocol_group.add_argument("--quic-max-datagram-size", type=int, default=None)
    protocol_group.add_argument("--quic-idle-timeout", type=float, default=None)
    protocol_group.add_argument("--quic-early-data-policy", choices=["allow", "deny", "require"], default=None)
    protocol_group.add_argument("--pipe-mode", choices=["rawframed", "stream"], default=None)
    protocol_group.add_argument("--quic-secret", default=None, help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    effective_argv = list(sys.argv[1:] if argv is None else argv)
    ns = parser.parse_args(effective_argv)
    config = build_config_from_namespace(ns)
    app_target = config.app.target or ns.app
    if not app_target:
        parser.error("an application import string is required (either as APP or in the config file)")

    if config.app.reload and not PollingReloader.is_child_process():
        reloader = PollingReloader(effective_argv, config=config)
        return reloader.run()

    if config.process.workers > 1 and os.environ.get('TIGRCORN_INTERNAL_RELOADER_CHILD') != '1':
        supervisor = ServerSupervisor(app_target=app_target, config=config)
        supervisor.run()
        return 0

    asyncio.run(
        serve_import_string(
            app_target,
            host=ns.host or config.listeners[0].host,
            port=ns.port or config.listeners[0].port,
            uds=ns.uds,
            transport=ns.transport or config.listeners[0].kind,
            lifespan=config.app.lifespan,
            log_level=config.logging.level,
            access_log=config.logging.access_log,
            ssl_certfile=config.tls.certfile,
            ssl_keyfile=config.tls.keyfile,
            ssl_ca_certs=config.tls.ca_certs,
            ssl_require_client_cert=config.tls.require_client_cert,
            ssl_ciphers=config.tls.ciphers,
            http_versions=config.http.http_versions,
            websocket=config.websocket.enabled,
            enable_h2c=config.http.enable_h2c,
            max_body_size=config.http.max_body_size,
            protocols=ns.protocols or list(config.listeners[0].protocols),
            quic_require_retry=config.quic.require_retry,
            pipe_mode=config.listeners[0].pipe_mode,
            config=config,
            factory=config.app.factory,
        )
    )
    return 0
