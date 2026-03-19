from __future__ import annotations

import argparse
import asyncio

from tigrcorn.api import serve_import_string


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tigrcorn", description="ASGI3-compatible transport server")
    parser.add_argument("app", help="Application import string in module:attr form")
    parser.add_argument("--transport", choices=["tcp", "udp", "unix", "pipe"], default="tcp")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host for TCP/UDP listeners")
    parser.add_argument("--port", default=8000, type=int, help="Bind port for TCP/UDP listeners")
    parser.add_argument("--uds", default=None, help="Bind Unix domain socket or pipe path instead of TCP/UDP")
    parser.add_argument("--lifespan", choices=["auto", "on", "off"], default="auto")
    parser.add_argument("--log-level", default="info")
    parser.add_argument("--no-access-log", action="store_true")
    parser.add_argument("--factory", action="store_true", help="Treat APP as an application factory")
    parser.add_argument("--ssl-certfile", help="Certificate for TLS on TCP/Unix or QUIC-TLS on UDP")
    parser.add_argument("--ssl-keyfile", help="Private key for TLS on TCP/Unix or QUIC-TLS on UDP")
    parser.add_argument("--ssl-ca-certs", help="Trusted CA bundle for TLS or QUIC-TLS client certificate verification")
    parser.add_argument("--ssl-require-client-cert", action="store_true", help="Require peer client certificates for TLS or QUIC-TLS listeners")
    parser.add_argument("--http", dest="http_versions", action="append", choices=["1.1", "2", "3"], help="Enable an HTTP version")
    parser.add_argument("--protocol", dest="protocols", action="append", choices=["http1", "http2", "http3", "quic", "websocket", "rawframed", "custom"], help="Enable a listener protocol")
    parser.add_argument("--disable-websocket", action="store_true")
    parser.add_argument("--disable-h2c", action="store_true")
    parser.add_argument("--max-body-size", type=int, default=None)
    parser.add_argument("--quic-secret", default=None, help="Shared secret for local QUIC experiments when not using QUIC-TLS certificates")
    parser.add_argument("--quic-require-retry", action="store_true", help="Require a QUIC Retry before completing the initial handshake")
    parser.add_argument("--pipe-mode", choices=["rawframed", "stream"], default="rawframed")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    ns = parser.parse_args(argv)
    asyncio.run(
        serve_import_string(
            ns.app,
            host=ns.host,
            port=ns.port,
            uds=ns.uds,
            transport=ns.transport,
            lifespan=ns.lifespan,
            log_level=ns.log_level,
            access_log=not ns.no_access_log,
            ssl_certfile=ns.ssl_certfile,
            ssl_keyfile=ns.ssl_keyfile,
            ssl_ca_certs=ns.ssl_ca_certs,
            ssl_require_client_cert=ns.ssl_require_client_cert,
            http_versions=ns.http_versions,
            websocket=not ns.disable_websocket,
            enable_h2c=not ns.disable_h2c,
            max_body_size=ns.max_body_size,
            protocols=ns.protocols,
            quic_secret=ns.quic_secret.encode('utf-8') if ns.quic_secret else None,
            quic_require_retry=ns.quic_require_retry,
            pipe_mode=ns.pipe_mode,
            factory=ns.factory,
        )
    )
    return 0
