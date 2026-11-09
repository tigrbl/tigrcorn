from __future__ import annotations

import unittest

from tigrcorn.app_interfaces import AppInterfaceError, normalize_app_interface, resolve_app_dispatch
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

    def test_runtime_selector_rejects_unknown_interface_even_if_app_is_valid(self) -> None:
        async def app(scope, receive, send):
            return None

        with self.assertRaises(AppInterfaceError):
            resolve_app_dispatch(app, "wsgi")  # type: ignore[arg-type]

    def test_interface_normalizer_is_fail_closed_and_accepts_canonical_aliases(self) -> None:
        self.assertEqual(normalize_app_interface("tigr_asgi_contract"), "tigr-asgi-contract")
        self.assertEqual(normalize_app_interface(None), "auto")

        with self.assertRaises(AppInterfaceError):
            normalize_app_interface("asgi2")
