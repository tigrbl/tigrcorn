import unittest

from tigrcorn.protocols.lifespan.driver import LifespanManager


class LifespanTests(unittest.IsolatedAsyncioTestCase):
    async def test_lifespan_start_stop(self):
        events = []

        async def app(scope, receive, send):
            self.assertEqual(scope["type"], "lifespan")
            msg = await receive()
            events.append(msg["type"])
            await send({"type": "lifespan.startup.complete"})
            msg = await receive()
            events.append(msg["type"])
            await send({"type": "lifespan.shutdown.complete"})

        manager = LifespanManager(app, mode="on")
        await manager.startup()
        await manager.shutdown()
        self.assertEqual(events, ["lifespan.startup", "lifespan.shutdown"])


if __name__ == "__main__":
    unittest.main()
