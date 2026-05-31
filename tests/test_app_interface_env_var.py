from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from tigrcorn.config.load import build_config_from_sources


class AppInterfaceEnvVarTests(unittest.TestCase):
    def test_flat_env_var_configures_app_interface(self) -> None:
        with patch.dict(os.environ, {"TIGRCORN_APP_INTERFACE": "asgi3"}, clear=False):
            config = build_config_from_sources()

        self.assertEqual(config.app.interface, "asgi3")

    def test_configured_env_prefix_controls_app_interface_env_var(self) -> None:
        with patch.dict(os.environ, {"ALT_APP_INTERFACE": "tigr-asgi-contract"}, clear=False):
            config = build_config_from_sources(env_prefix="ALT")

        self.assertEqual(config.app.interface, "tigr-asgi-contract")
