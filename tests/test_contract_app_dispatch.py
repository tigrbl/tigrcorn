from __future__ import annotations

import asyncio
import unittest

from tigrcorn.app_interfaces import native_contract_app, resolve_app_dispatch


class ContractAppDispatchTests(unittest.TestCase):
    def test_contract_dispatch_invokes_native_handle_directly(self) -> None:
        seen = []

        class NativeApp:
            async def handle(self, scope, receive, send):
                seen.append(("handle", scope["type"]))
                await send({"type": "native.response", "ok": True})

        async def run_dispatch() -> list[dict]:
            sent: list[dict] = []
            async def send(message: dict) -> None:
                sent.append(message)

            selection = resolve_app_dispatch(native_contract_app(NativeApp()), "tigr-asgi-contract")
            await selection.app({"type": "tigrcorn.contract"}, lambda: None, send)
            return sent

        sent = asyncio.run(run_dispatch())

        self.assertEqual(seen, [("handle", "tigrcorn.contract")])
        self.assertEqual(sent, [{"type": "native.response", "ok": True}])
