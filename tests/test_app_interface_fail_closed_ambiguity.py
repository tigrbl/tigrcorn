from __future__ import annotations

import unittest

from tigrcorn.app_interfaces import AppInterfaceError, resolve_app_dispatch
from tigrcorn.config.load import config_from_mapping
from tigrcorn.errors import ConfigError


class AppInterfaceFailClosedAmbiguityTests(unittest.TestCase):
    def test_asgi2_shape_fails_closed_in_auto_mode(self) -> None:
        def asgi2(scope, receive):
            return None

        with self.assertRaises(AppInterfaceError):
            resolve_app_dispatch(asgi2, "auto")

    def test_invalid_configured_interface_fails_validation(self) -> None:
        with self.assertRaises(ConfigError):
            config_from_mapping({"app": {"interface": "wsgi"}})
