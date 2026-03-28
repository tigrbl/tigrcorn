from __future__ import annotations


async def app(scope, receive, send):
    assert scope['type'] == 'http'
    while True:
        message = await receive()
        if message['type'] == 'http.request' and not message.get('more_body', False):
            break
        if message['type'] == 'http.disconnect':
            return
    await send(
        {
            'type': 'http.response.start',
            'status': 103,
            'headers': [
                (b'link', b'</static/app.css>; rel=preload; as=style'),
                (b'x-ignored', b'not-safe-for-early-hints'),
            ],
        }
    )
    await send(
        {
            'type': 'http.response.start',
            'status': 200,
            'headers': [(b'content-type', b'text/plain; charset=utf-8')],
        }
    )
    await send({'type': 'http.response.body', 'body': b'phase4 early hints', 'more_body': False})
