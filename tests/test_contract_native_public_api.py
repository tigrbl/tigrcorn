from __future__ import annotations

import unittest

import tigrcorn
from tigrcorn.app_interfaces import NativeContractApp, is_native_contract_app, mark_native_contract_app, native_contract_app


class ContractNativePublicAPITests(unittest.TestCase):
    def test_public_native_helpers_register_metadata_and_capabilities(self) -> None:
        class NativeApp:
            async def handle(self, scope, receive, send):
                return None

        wrapped = native_contract_app(NativeApp(), capabilities=["http"], metadata={"name": "demo"})

        self.assertIsInstance(wrapped, NativeContractApp)
        self.assertTrue(is_native_contract_app(wrapped))
        self.assertEqual(wrapped.capabilities, ("http",))
        self.assertEqual(wrapped.metadata["name"], "demo")
        self.assertIs(tigrcorn.NativeContractApp, NativeContractApp)

    def test_public_marker_declares_native_interface_without_asgi_signature(self) -> None:
        class NativeApp:
            async def handle(self, scope, receive, send):
                return None

        app = mark_native_contract_app(NativeApp(), capabilities=["webtransport"])

        self.assertTrue(is_native_contract_app(app))
        self.assertEqual(app.__tigrcorn_contract_capabilities__, ("webtransport",))
