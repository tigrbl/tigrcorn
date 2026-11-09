from __future__ import annotations

import inspect
import unittest

from tigrcorn.api import run, serve, serve_import_string
from tigrcorn.app_interfaces import native_contract_app
from tigrcorn.config.load import build_config
from tigrcorn.server.runner import TigrCornServer


class AppInterfacePublicAPITests(unittest.TestCase):
    def test_build_config_accepts_public_app_interface_selector(self) -> None:
        config = build_config(app_interface="tigr-asgi-contract")

        self.assertEqual(config.app.interface, "tigr-asgi-contract")

    def test_startup_api_signatures_expose_app_interface_selector(self) -> None:
        for callable_obj in (run, serve, serve_import_string):
            self.assertIn("app_interface", inspect.signature(callable_obj).parameters)

    def test_server_exposes_resolved_public_dispatch_metadata(self) -> None:
        class NativeApp:
            async def handle(self, scope, receive, send):
                return None

        config = build_config(app_interface="tigr-asgi-contract")
        server = TigrCornServer(native_contract_app(NativeApp()), config)

        self.assertEqual(server.app_interface, "tigr-asgi-contract")
        self.assertEqual(server.app_interface_source, "explicit")
        self.assertEqual(server.app_dispatch_selection.as_metadata()["requested_interface"], "tigr-asgi-contract")
