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
