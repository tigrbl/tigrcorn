from __future__ import annotations

import unittest

from tigrcorn.cli import build_parser
from tigrcorn.config.load import build_config_from_namespace


class AppInterfaceCLIFlagTests(unittest.TestCase):
    def test_cli_flag_selects_app_interface(self) -> None:
        parser = build_parser()
        ns = parser.parse_args(["tests.fixtures_pkg.appmod:app", "--app-interface", "tigr-asgi-contract"])
        config = build_config_from_namespace(ns)

        self.assertEqual(ns.app_interface, "tigr-asgi-contract")
        self.assertEqual(config.app.interface, "tigr-asgi-contract")

    def test_cli_rejects_unsupported_app_interface_before_runtime_dispatch(self) -> None:
        parser = build_parser()

        with self.assertRaises(SystemExit):
            parser.parse_args(["tests.fixtures_pkg.appmod:app", "--app-interface", "wsgi"])

    def test_cli_selector_normalizes_into_config_without_runtime_introspection(self) -> None:
        parser = build_parser()
        ns = parser.parse_args(["tests.fixtures_pkg.appmod:app", "--app-interface", "asgi3"])
        config = build_config_from_namespace(ns)

        self.assertEqual(config.app.interface, "asgi3")
