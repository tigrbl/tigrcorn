from __future__ import annotations

import inspect
import unittest

from tigrcorn.api import run, serve, serve_import_string
from tigrcorn.config.load import build_config


class AppInterfacePublicAPITests(unittest.TestCase):
    def test_build_config_accepts_public_app_interface_selector(self) -> None:
        config = build_config(app_interface="tigr-asgi-contract")

        self.assertEqual(config.app.interface, "tigr-asgi-contract")

    def test_startup_api_signatures_expose_app_interface_selector(self) -> None:
        for callable_obj in (run, serve, serve_import_string):
            self.assertIn("app_interface", inspect.signature(callable_obj).parameters)
