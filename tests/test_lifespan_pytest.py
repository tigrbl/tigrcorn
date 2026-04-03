
from tigrcorn.protocols.lifespan.driver import LifespanManager


import pytest
class TestLifespanTests:
    async def test_lifespan_start_stop(self):
        events = []

        async def app(scope, receive, send):
            assert scope["type"] == "lifespan"
            msg = await receive()
            events.append(msg["type"])
            await send({"type": "lifespan.startup.complete"})
            msg = await receive()
            events.append(msg["type"])
            await send({"type": "lifespan.shutdown.complete"})

        manager = LifespanManager(app, mode="on")
        await manager.startup()
        await manager.shutdown()
        assert events == ["lifespan.startup", "lifespan.shutdown"]
