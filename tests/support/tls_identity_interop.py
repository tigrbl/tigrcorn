from __future__ import annotations

import asyncio
import ssl
from datetime import datetime, timezone
from pathlib import Path

from tigrcorn.config.load import build_config
from tigrcorn.server.runner import TigrCornServer

ROOT = Path(__file__).resolve().parents[1]
CERTS = ROOT / 'fixtures_certs'
SERVER_CERT = CERTS / 'interop-localhost-cert.pem'
SERVER_KEY = CERTS / 'interop-localhost-key.pem'
RELEASE_ROOT = ROOT.parent / 'docs' / 'review' / 'conformance' / 'releases' / '0.3.9' / 'release-0.3.9'
INDEPENDENT = RELEASE_ROOT / 'tigrcorn-independent-certification-release-matrix'
_NOW = datetime.now(timezone.utc)


async def _start_tls_server(app, *, http_versions: list[str] | None = None) -> tuple[TigrCornServer, int]:
    config = build_config(
        host='127.0.0.1',
        port=0,
        lifespan='off',
        http_versions=http_versions or ['1.1'],
        ssl_certfile=str(SERVER_CERT),
        ssl_keyfile=str(SERVER_KEY),
    )
    server = TigrCornServer(app, config)
    await server.start()
    listener = server._listeners[0]
    port = listener.server.sockets[0].getsockname()[1]
    return server, port


def _client_context(*, alpn: list[str]) -> ssl.SSLContext:
    context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=str(SERVER_CERT))
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    context.set_alpn_protocols(alpn)
    return context


class _FakeWriter:
    def __init__(self) -> None:
        self.records: list[bytes] = []
        self.closed = False

    def write(self, data: bytes) -> None:
        self.records.append(data)

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        return None

    def is_closing(self) -> bool:
        return self.closed

    def get_extra_info(self, name: str, default=None):
        return default


class _FakeReader(asyncio.StreamReader):
    pass

