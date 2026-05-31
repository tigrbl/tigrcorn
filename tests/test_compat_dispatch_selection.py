from __future__ import annotations

import unittest

from tigrcorn.app_interfaces import AppInterfaceError, mark_native_contract_app, resolve_app_dispatch


class CompatDispatchSelectionTests(unittest.TestCase):
    def test_auto_selects_native_marker_before_signature_introspection(self) -> None:
        class NativeApp:
            async def handle(self, scope, receive, send):
                return None

        selection = resolve_app_dispatch(mark_native_contract_app(NativeApp()), "auto")

        self.assertEqual(selection.interface, "tigr-asgi-contract")
        self.assertTrue(selection.native)

    def test_auto_selects_unambiguous_asgi3_callable(self) -> None:
        async def app(scope, receive, send):
            return None

        selection = resolve_app_dispatch(app, "auto")

        self.assertEqual(selection.interface, "asgi3")
        self.assertFalse(selection.native)

    def test_auto_fails_closed_for_ambiguous_callable(self) -> None:
        def ambiguous(*args):
            return None

        with self.assertRaises(AppInterfaceError):
            resolve_app_dispatch(ambiguous, "auto")
