from __future__ import annotations

import unittest
from unittest.mock import patch

from tigrcorn.app_interfaces import native_contract_app
from tigrcorn.config.load import build_config
from tigrcorn.server.runner import TigrCornServer


class ASGI3HotPathIsolationTests(unittest.TestCase):
    def test_native_server_construction_does_not_call_asgi3_assertion(self) -> None:
        class NativeApp:
            async def handle(self, scope, receive, send):
                return None

        config = build_config(app_interface="tigr-asgi-contract")
        with patch("tigrcorn.app_interfaces.assert_asgi3_app", side_effect=AssertionError("asgi3 path used")):
            server = TigrCornServer(native_contract_app(NativeApp()), config)

        self.assertEqual(server.app_interface, "tigr-asgi-contract")
