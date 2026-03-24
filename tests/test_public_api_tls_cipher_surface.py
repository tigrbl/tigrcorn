from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from tigrcorn.api import serve
from tigrcorn.cli import main
from tigrcorn.config.load import build_config


class PublicAPITLSCipherSurfaceTests(unittest.TestCase):
    def test_serve_forwards_ssl_ciphers(self):
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
        self.assertEqual(build_config_mock.call_args.kwargs['ssl_ciphers'], 'TLS_AES_128_GCM_SHA256')
        fake_server.serve_forever.assert_awaited_once()


class PublicCLITLSCipherSurfaceTests(unittest.TestCase):
    def test_cli_main_forwards_ssl_ciphers(self):
        real_asyncio_run = asyncio.run
        serve_import_string = AsyncMock()
        with (
            patch('tigrcorn.cli.serve_import_string', new=serve_import_string),
            patch('tigrcorn.cli.asyncio.run', side_effect=real_asyncio_run),
        ):
            rc = main([
                'tests.fixtures_pkg.appmod:app',
                '--ssl-certfile', 'server-cert.pem',
                '--ssl-keyfile', 'server-key.pem',
                '--ssl-ciphers', 'TLS_AES_128_GCM_SHA256',
            ])
        self.assertEqual(rc, 0)
        serve_import_string.assert_awaited_once()
        self.assertEqual(serve_import_string.await_args.kwargs['ssl_ciphers'], 'TLS_AES_128_GCM_SHA256')


if __name__ == '__main__':
    unittest.main()
