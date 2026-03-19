from __future__ import annotations


async def app(scope, receive, send):
    assert scope['type'] == 'websocket'
    connect = await receive()
    assert connect['type'] == 'websocket.connect'
    await send({'type': 'websocket.accept', 'subprotocol': 'chat', 'headers': []})
    event = await receive()
    if event.get('text') is not None:
        await send({'type': 'websocket.send', 'text': event['text']})
    elif event.get('bytes') is not None:
        await send({'type': 'websocket.send', 'bytes': event['bytes']})
    await send({'type': 'websocket.close', 'code': 1000, 'reason': ''})
