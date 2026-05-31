from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from tigrcorn.config.load import config_from_source


class AppInterfaceConfigTOMLTests(unittest.TestCase):
    def test_toml_app_interface_key_configures_dispatch_mode(self) -> None:
        with tempfile.TemporaryDirectory(dir=os.getcwd()) as tmp:
            path = Path(tmp) / "tigrcorn.toml"
            path.write_text('[app]\ntarget = "tests.fixtures_pkg.appmod:app"\ninterface = "asgi3"\n', encoding="utf-8")

            config = config_from_source(path)

        self.assertEqual(config.app.interface, "asgi3")
