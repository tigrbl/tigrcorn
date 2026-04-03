from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from tigrcorn.api import serve
from tigrcorn.cli import main
from tigrcorn.config.load import build_config


import pytest

def test_serve_forwards_ssl_ciphers():
    async def _app(scope, receive, send):
        return None

    fake_server = MagicMock()
    fake_server.serve_forever = AsyncMock(return_value=None)
    fake_server.request_shutdown = MagicMock()
    with (
        patch('tigrcorn.api.build_config', wraps=build_config) as build_config_mock,
        patch('tigrcorn.api.TigrCornServer', return_value=fake_server),
        patch('tigrcorn.api.install_signal_handlers', return_value=None),
    ):
        asyncio.run(serve(_app, ssl_ciphers='TLS_AES_128_GCM_SHA256'))

    build_config_mock.assert_called_once()
    assert build_config_mock.call_args.kwargs['ssl_ciphers'] == 'TLS_AES_128_GCM_SHA256'
    fake_server.serve_forever.assert_awaited_once()



def test_cli_main_forwards_ssl_ciphers():
    with patch('tigrcorn.cli.run_config') as run_config:
        rc = main([
            'tests.fixtures_pkg.appmod:app',
            '--ssl-certfile', 'server-cert.pem',
            '--ssl-keyfile', 'server-key.pem',
            '--ssl-ciphers', 'TLS_AES_128_GCM_SHA256',
        ])
    assert rc == 0
    run_config.assert_called_once()
    config = run_config.call_args.args[0]
    assert config.app.target == 'tests.fixtures_pkg.appmod:app'
    assert config.tls.ciphers == 'TLS_AES_128_GCM_SHA256'
    assert config.listeners[0].ssl_ciphers == 'TLS_AES_128_GCM_SHA256'
