from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from tigrcorn import api
from tigrcorn.cli import main


import pytest
async def _app(scope, receive, send):
    return None


class TestPublicAPIClientCertificateSurfaceTests:
    async def test_serve_builds_config_with_client_certificate_options(self):
        config = object()
        server = SimpleNamespace(serve_forever=AsyncMock(), request_shutdown=object())
        with (
            patch('tigrcorn.api.build_config', return_value=config) as build_config,
            patch('tigrcorn.api.TigrCornServer', return_value=server) as server_type,
            patch('tigrcorn.api.install_signal_handlers') as install_signal_handlers,
        ):
            await api.serve(
                _app,
                transport='udp',
                protocols=['http3'],
                http_versions=['3'],
                ssl_certfile='server-cert.pem',
                ssl_keyfile='server-key.pem',
                ssl_ca_certs='client-ca.pem',
                ssl_require_client_cert=True,
            )

        assert build_config.call_count == 1
        kwargs = build_config.call_args.kwargs
        assert kwargs['transport'] == 'udp'
        assert kwargs['protocols'] == ['http3']
        assert kwargs['http_versions'] == ['3']
        assert kwargs['ssl_certfile'] == 'server-cert.pem'
        assert kwargs['ssl_keyfile'] == 'server-key.pem'
        assert kwargs['ssl_ca_certs'] == 'client-ca.pem'
        assert kwargs['ssl_require_client_cert']
        server_type.assert_called_once_with(app=_app, config=config)
        install_signal_handlers.assert_called_once()
        server.serve_forever.assert_awaited_once()

    async def test_serve_import_string_forwards_client_certificate_options(self):
        serve = AsyncMock()
        with (
            patch('tigrcorn.api.load_app', return_value=_app) as load_app,
            patch('tigrcorn.api.serve', new=serve),
        ):
            await api.serve_import_string(
                'tests.fixtures_pkg.appmod:app',
                transport='udp',
                protocols=['http3'],
                http_versions=['3'],
                ssl_certfile='server-cert.pem',
                ssl_keyfile='server-key.pem',
                ssl_ca_certs='client-ca.pem',
                ssl_require_client_cert=True,
                factory=True,
            )

        load_app.assert_called_once_with('tests.fixtures_pkg.appmod:app', factory=True)
        serve.assert_awaited_once()
        kwargs = serve.await_args.kwargs
        assert kwargs['transport'] == 'udp'
        assert kwargs['protocols'] == ['http3']
        assert kwargs['http_versions'] == ['3']
        assert kwargs['ssl_certfile'] == 'server-cert.pem'
        assert kwargs['ssl_keyfile'] == 'server-key.pem'
        assert kwargs['ssl_ca_certs'] == 'client-ca.pem'
        assert kwargs['ssl_require_client_cert']
class TestPublicRunAndCLIClientCertificateSurfaceTests:
    def test_run_with_import_string_forwards_client_certificate_options(self):
        real_asyncio_run = asyncio.run
        serve_import_string = AsyncMock()
        with (
            patch('tigrcorn.api.serve_import_string', new=serve_import_string),
            patch('tigrcorn.api.asyncio.run', side_effect=real_asyncio_run),
        ):
            api.run(
                'tests.fixtures_pkg.appmod:app',
                transport='udp',
                protocols=['http3'],
                http_versions=['3'],
                ssl_certfile='server-cert.pem',
                ssl_keyfile='server-key.pem',
                ssl_ca_certs='client-ca.pem',
                ssl_require_client_cert=True,
                factory=True,
            )

        serve_import_string.assert_awaited_once()
        args = serve_import_string.await_args.args
        kwargs = serve_import_string.await_args.kwargs
        assert args == ('tests.fixtures_pkg.appmod:app',)
        assert kwargs['transport'] == 'udp'
        assert kwargs['protocols'] == ['http3']
        assert kwargs['http_versions'] == ['3']
        assert kwargs['ssl_certfile'] == 'server-cert.pem'
        assert kwargs['ssl_keyfile'] == 'server-key.pem'
        assert kwargs['ssl_ca_certs'] == 'client-ca.pem'
        assert kwargs['ssl_require_client_cert']
        assert kwargs['factory']
    def test_run_with_app_instance_forwards_client_certificate_options(self):
        real_asyncio_run = asyncio.run
        serve = AsyncMock()
        with (
            patch('tigrcorn.api.serve', new=serve),
            patch('tigrcorn.api.asyncio.run', side_effect=real_asyncio_run),
        ):
            api.run(
                _app,
                transport='udp',
                protocols=['http3'],
                http_versions=['3'],
                ssl_certfile='server-cert.pem',
                ssl_keyfile='server-key.pem',
                ssl_ca_certs='client-ca.pem',
                ssl_require_client_cert=True,
            )

        serve.assert_awaited_once()
        args = serve.await_args.args
        kwargs = serve.await_args.kwargs
        assert args == (_app,)
        assert kwargs['transport'] == 'udp'
        assert kwargs['protocols'] == ['http3']
        assert kwargs['http_versions'] == ['3']
        assert kwargs['ssl_certfile'] == 'server-cert.pem'
        assert kwargs['ssl_keyfile'] == 'server-key.pem'
        assert kwargs['ssl_ca_certs'] == 'client-ca.pem'
        assert kwargs['ssl_require_client_cert']
    def test_cli_main_forwards_client_certificate_options(self):
        with patch('tigrcorn.cli.run_config') as run_config:
            rc = main([
                'tests.fixtures_pkg.appmod:app',
                '--transport', 'udp',
                '--protocol', 'http3',
                '--http', '3',
                '--ssl-certfile', 'server-cert.pem',
                '--ssl-keyfile', 'server-key.pem',
                '--ssl-ca-certs', 'client-ca.pem',
                '--ssl-require-client-cert',
                '--factory',
            ])

        assert rc == 0
        run_config.assert_called_once()
        config = run_config.call_args.args[0]
        listener = config.listeners[0]
        assert config.app.target == 'tests.fixtures_pkg.appmod:app'
        assert config.app.factory
        assert listener.kind == 'udp'
        assert listener.protocols == ['quic', 'http3']
        assert listener.http_versions == ['3']
        assert listener.ssl_certfile == 'server-cert.pem'
        assert listener.ssl_keyfile == 'server-key.pem'
        assert listener.ssl_ca_certs == 'client-ca.pem'
        assert listener.ssl_require_client_cert
