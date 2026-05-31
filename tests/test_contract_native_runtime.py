from __future__ import annotations

import unittest

from tigrcorn.app_interfaces import native_contract_app
from tigrcorn.config.load import build_config
from tigrcorn.server.runner import TigrCornServer


class ContractNativeRuntimeTests(unittest.TestCase):
    def test_native_runtime_accepts_non_asgi3_contract_app(self) -> None:
        class NativeApp:
            async def handle(self, scope, receive, send):
                await send({"type": "native.complete"})

        config = build_config(app_interface="tigr-asgi-contract")
        server = TigrCornServer(native_contract_app(NativeApp()), config)

        self.assertEqual(server.app_interface, "tigr-asgi-contract")
        self.assertTrue(callable(server.app))
