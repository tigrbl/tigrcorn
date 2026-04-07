from __future__ import annotations

import argparse
import os
import sys

from tigrcorn.config.policy_surface import flag_help
from tigrcorn.config.quic_surface import quic_flag_help
from tigrcorn.config.load import build_config_from_namespace
from tigrcorn.constants import SUPPORTED_RUNTIMES
from tigrcorn.server.bootstrap import run_config
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
    app_group.add_argument("--worker-class", default=None, help="Worker implementation class")
    app_group.add_argument("--runtime", choices=list(SUPPORTED_RUNTIMES), default=None, help="Runtime backend for sync entrypoints and worker processes")
    app_group.add_argument("--pid", default=None, help="PID file path")
    app_group.add_argument("--worker-healthcheck-timeout", type=float, default=None, help="Worker startup healthcheck timeout in seconds")
    app_group.add_argument("--config", default=None, help="Config source: file path (.json, .toml, .yaml, .yml, .py), module:<module>, or object:<module>:<name>")
    app_group.add_argument("--env-file", dest="env_file", default=None, help="Load additional prefixed config values from a dotenv file")
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
    bind_group.add_argument("--user", default=None, help="User name or uid to own Unix sockets")
    bind_group.add_argument("--group", default=None, help="Group name or gid to own Unix sockets")
    bind_group.add_argument("--umask", default=None, help="Umask applied while creating Unix sockets (octal or integer)")

    static_group = parser.add_argument_group("Static / delivery")
    static_group.add_argument("--static-path-route", dest="static_path_route", default=None, help="HTTP route prefix served from the mounted static directory")
    static_group.add_argument("--static-path-mount", dest="static_path_mount", default=None, help="Filesystem directory mounted at --static-path-route")
    _add_flag_pair(static_group, "--static-path-dir-to-file", "--no-static-path-dir-to-file", dest="static_path_dir_to_file", help_text="directory index resolution for the mounted static path")
    static_group.add_argument("--static-path-index-file", dest="static_path_index_file", default=None, help="Index file name served when directory index resolution is enabled")
    static_group.add_argument("--static-path-expires", dest="static_path_expires", type=int, default=None, help="Static-response cache TTL in seconds; 0 disables caching headers")

    tls_group = parser.add_argument_group("TLS / security")
    tls_group.add_argument("--ssl-certfile", default=None, help="Certificate for TLS on TCP/Unix or QUIC-TLS on UDP")
    tls_group.add_argument("--ssl-keyfile", default=None, help="Private key for TLS on TCP/Unix or QUIC-TLS on UDP")
    tls_group.add_argument("--ssl-keyfile-password", default=None, help="Password for an encrypted private key PEM used by package-owned TLS/QUIC-TLS listeners")
    tls_group.add_argument("--ssl-ca-certs", default=None, help="Trusted CA bundle for client-certificate verification")
    tls_group.add_argument("--ssl-require-client-cert", action="store_true", default=None, help="Require peer client certificates")
    tls_group.add_argument("--ssl-ciphers", default=None)
    tls_group.add_argument("--ssl-alpn", action="append", default=None, help=flag_help("--ssl-alpn", "ALPN protocol(s); repeat or use comma-separated values"))
    tls_group.add_argument("--ssl-ocsp-mode", choices=["off", "soft-fail", "require"], default=None, help=flag_help("--ssl-ocsp-mode"))
    tls_group.add_argument("--ssl-ocsp-soft-fail", action="store_true", default=None, help=flag_help("--ssl-ocsp-soft-fail"))
    tls_group.add_argument("--ssl-ocsp-cache-size", type=int, default=None, help=flag_help("--ssl-ocsp-cache-size"))
    tls_group.add_argument("--ssl-ocsp-max-age", type=float, default=None, help=flag_help("--ssl-ocsp-max-age"))
    tls_group.add_argument("--ssl-crl-mode", choices=["off", "soft-fail", "require"], default=None, help=flag_help("--ssl-crl-mode"))
    tls_group.add_argument("--ssl-crl", default=None, help=flag_help("--ssl-crl", "Local CRL file (PEM or DER) loaded into the package-owned revocation material set"))
    tls_group.add_argument("--ssl-revocation-fetch", choices=["off", "on"], default=None, help=flag_help("--ssl-revocation-fetch"))
    tls_group.add_argument("--proxy-headers", action="store_true", default=None, help=flag_help("--proxy-headers"))
    tls_group.add_argument("--forwarded-allow-ips", action="append", default=None, help=flag_help("--forwarded-allow-ips", "Trusted forwarded-header peers; repeat or use comma-separated values"))
    tls_group.add_argument("--root-path", default=None, help=flag_help("--root-path", "ASGI root_path mount prefix"))
    tls_group.add_argument("--server-header", nargs="?", const="tigrcorn", default=None, help="Enable or override the Server header value")
    tls_group.add_argument("--no-server-header", action="store_true", default=False, help="Disable the Server header")
    _add_flag_pair(tls_group, "--date-header", "--no-date-header", dest="date_header", help_text="Date header injection")
    tls_group.add_argument("--header", dest="headers", action="append", default=None, help="Default response header in name:value form; repeat to add multiple headers")
    tls_group.add_argument("--server-name", action="append", default=None, help="Allowed Host/:authority value; repeat or use comma-separated values")

    log_group = parser.add_argument_group("Logging / observability")
    log_group.add_argument("--log-level", default=None)
    _add_flag_pair(log_group, "--access-log", "--no-access-log", dest="access_log", help_text="Access logging")
    log_group.add_argument("--access-log-file", default=None)
    log_group.add_argument("--access-log-format", default=None)
    log_group.add_argument("--error-log-file", default=None)
    log_group.add_argument("--log-config", default=None)
    log_group.add_argument("--structured-log", action="store_true", default=None)
    _add_flag_pair(log_group, "--use-colors", "--no-use-colors", dest="use_colors", help_text="Colorized logging")
    log_group.add_argument("--metrics", action="store_true", default=None)
    log_group.add_argument("--metrics-bind", default=None)
    log_group.add_argument("--statsd-host", default=None)
    log_group.add_argument("--otel-endpoint", default=None)

    limit_group = parser.add_argument_group("Resource / timeouts / concurrency")
    limit_group.add_argument("--timeout-keep-alive", type=float, default=None, help=flag_help("--timeout-keep-alive"))
    limit_group.add_argument("--read-timeout", type=float, default=None, help=flag_help("--read-timeout"))
    limit_group.add_argument("--write-timeout", type=float, default=None, help=flag_help("--write-timeout"))
    limit_group.add_argument("--timeout-graceful-shutdown", type=float, default=None, help=flag_help("--timeout-graceful-shutdown"))
    limit_group.add_argument("--limit-concurrency", type=int, default=None, help=flag_help("--limit-concurrency"))
    limit_group.add_argument("--max-connections", type=int, default=None, help=flag_help("--max-connections"))
    limit_group.add_argument("--max-tasks", type=int, default=None, help=flag_help("--max-tasks"))
    limit_group.add_argument("--max-streams", type=int, default=None, help=flag_help("--max-streams"))
    limit_group.add_argument("--max-body-size", type=int, default=None, help=flag_help("--max-body-size"))
    limit_group.add_argument("--max-header-size", type=int, default=None, help=flag_help("--max-header-size"))
    limit_group.add_argument("--http1-max-incomplete-event-size", type=int, default=None, help=flag_help("--http1-max-incomplete-event-size", "Cap buffered incomplete HTTP/1.1 request-head bytes before the parser rejects the request"))
    limit_group.add_argument("--http1-buffer-size", type=int, default=None, help=flag_help("--http1-buffer-size", "Read-buffer size used for HTTP/1.1 request-head/body incremental reads"))
    limit_group.add_argument("--http1-header-read-timeout", type=float, default=None, help=flag_help("--http1-header-read-timeout", "HTTP/1.1 request-head read timeout in seconds; when set it tightens the generic read/keep-alive timeout"))
    _add_flag_pair(limit_group, "--http1-keep-alive", "--no-http1-keep-alive", dest="http1_keep_alive", help_text=flag_help("--http1-keep-alive", "HTTP/1.1 connection persistence"))
    limit_group.add_argument("--http2-max-concurrent-streams", type=int, default=None, help=flag_help("--http2-max-concurrent-streams", "Advertised HTTP/2 MAX_CONCURRENT_STREAMS value for inbound peer-created streams"))
    limit_group.add_argument("--http2-max-headers-size", type=int, default=None, help=flag_help("--http2-max-headers-size", "HTTP/2-specific request-header and decoded header-list size cap"))
    limit_group.add_argument("--http2-max-frame-size", type=int, default=None, help=flag_help("--http2-max-frame-size", "Advertised HTTP/2 MAX_FRAME_SIZE for inbound peer frames"))
    _add_flag_pair(limit_group, "--http2-adaptive-window", "--no-http2-adaptive-window", dest="http2_adaptive_window", help_text=flag_help("--http2-adaptive-window", "HTTP/2 adaptive receive-window growth"))
    limit_group.add_argument("--http2-initial-connection-window-size", type=int, default=None, help=flag_help("--http2-initial-connection-window-size", "HTTP/2 connection-level receive window target; values below 65535 are clamped to the protocol default"))
    limit_group.add_argument("--http2-initial-stream-window-size", type=int, default=None, help=flag_help("--http2-initial-stream-window-size", "Advertised HTTP/2 INITIAL_WINDOW_SIZE for peer-created streams"))
    limit_group.add_argument("--http2-keep-alive-interval", type=float, default=None, help=flag_help("--http2-keep-alive-interval", "Idle interval before the server sends an HTTP/2 connection-level PING"))
    limit_group.add_argument("--http2-keep-alive-timeout", type=float, default=None, help=flag_help("--http2-keep-alive-timeout", "HTTP/2 keep-alive PING acknowledgement timeout in seconds"))
    limit_group.add_argument("--websocket-max-message-size", type=int, default=None, help=flag_help("--websocket-max-message-size"))
    limit_group.add_argument("--websocket-max-queue", type=int, default=None, help=flag_help("--websocket-max-queue", "Maximum queued inbound WebSocket messages before transport backpressure is applied"))
    limit_group.add_argument("--websocket-ping-interval", type=float, default=None, help=flag_help("--websocket-ping-interval"))
    limit_group.add_argument("--websocket-ping-timeout", type=float, default=None, help=flag_help("--websocket-ping-timeout"))
    limit_group.add_argument("--idle-timeout", type=float, default=None, help=flag_help("--idle-timeout"))

    protocol_group = parser.add_argument_group("Protocol / transport")
    protocol_group.add_argument("--http", dest="http_versions", action="append", choices=["1.1", "2", "3"], default=None, help="Enable an HTTP version")
    protocol_group.add_argument("--protocol", dest="protocols", action="append", choices=["http1", "http2", "http3", "quic", "websocket", "rawframed", "custom"], default=None, help="Enable a listener protocol")
    protocol_group.add_argument("--disable-websocket", action="store_true", default=None)
    protocol_group.add_argument("--disable-h2c", action="store_true", default=None, help=flag_help("--disable-h2c"))
    protocol_group.add_argument("--websocket-compression", choices=["off", "permessage-deflate"], default=None, help=flag_help("--websocket-compression"))
    protocol_group.add_argument("--connect-policy", choices=["relay", "deny", "allowlist"], default=None, help=flag_help("--connect-policy"))
    protocol_group.add_argument("--connect-allow", action="append", default=None, help=flag_help("--connect-allow", "Repeat or use comma-separated host:port, host, or CIDR entries"))
    protocol_group.add_argument("--trailer-policy", choices=["pass", "drop", "strict"], default=None, help=flag_help("--trailer-policy"))
    protocol_group.add_argument("--content-coding-policy", choices=["allowlist", "identity-only", "strict"], default=None, help=flag_help("--content-coding-policy"))
    protocol_group.add_argument("--content-codings", action="append", default=None, help=flag_help("--content-codings", "Repeat or use comma-separated values"))
    protocol_group.add_argument("--alt-svc", action="append", default=None, help="Advertise Alt-Svc values; repeat or use comma-separated values")
    _add_flag_pair(protocol_group, "--alt-svc-auto", "--no-alt-svc-auto", dest="alt_svc_auto", help_text="automatic Alt-Svc advertisement for HTTP/3-capable UDP listeners")
    protocol_group.add_argument("--alt-svc-ma", type=int, default=None, help="Alt-Svc max-age for automatic advertisement")
    protocol_group.add_argument("--alt-svc-persist", action="store_true", default=None, help="Set persist=1 on automatic Alt-Svc advertisements")
    protocol_group.add_argument("--quic-require-retry", action="store_true", default=None, help=quic_flag_help("--quic-require-retry"))
    protocol_group.add_argument("--quic-max-datagram-size", type=int, default=None, help=quic_flag_help("--quic-max-datagram-size"))
    protocol_group.add_argument("--quic-idle-timeout", type=float, default=None, help=quic_flag_help("--quic-idle-timeout"))
    protocol_group.add_argument("--quic-early-data-policy", choices=["allow", "deny", "require"], default=None, help=quic_flag_help("--quic-early-data-policy"))
    protocol_group.add_argument("--pipe-mode", choices=["rawframed", "stream"], default=None)
    protocol_group.add_argument("--quic-secret", default=None, help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Parse CLI arguments, build a ServerConfig, and hand off to run_config.

    The CLI entrypoint is intentionally config-driven. The stable import-string
    convenience surface lives in :mod:`tigrcorn.api` as ``serve_import_string``;
    the CLI does not re-expose that helper as a module-level patch seam.
    """
    parser = build_parser()
    effective_argv = list(sys.argv[1:] if argv is None else argv)
    ns = parser.parse_args(effective_argv)
    config = build_config_from_namespace(ns)
    app_target = config.app.target or ns.app
    if not app_target and not config.static_mount_enabled:
        parser.error("an application import string is required (either as APP or in the config file) unless a static mount is configured")

    if config.app.reload and not PollingReloader.is_child_process():
        reloader = PollingReloader(effective_argv, config=config)
        return reloader.run()

    if config.process.workers > 1 and os.environ.get('TIGRCORN_INTERNAL_RELOADER_CHILD') != '1':
        supervisor = ServerSupervisor(app_target=app_target, config=config)
        supervisor.run()
        return 0

    config.app.target = app_target
    run_config(config)
    return 0
