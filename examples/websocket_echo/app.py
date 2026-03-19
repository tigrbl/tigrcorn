from __future__ import annotations


async def app(scope, receive, send):
    assert scope["type"] == "websocket"
    event = await receive()
    assert event["type"] == "websocket.connect"
    await send({"type": "websocket.accept"})
    while True:
        event = await receive()
        if event["type"] == "websocket.disconnect":
            return
        if event.get("text") is not None:
            await send({"type": "websocket.send", "text": event["text"]})
        elif event.get("bytes") is not None:
            await send({"type": "websocket.send", "bytes": event["bytes"]})
