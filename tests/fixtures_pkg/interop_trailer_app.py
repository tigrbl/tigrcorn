from __future__ import annotations


async def app(scope, receive, send):
    # drain request body if present
    while True:
        message = await receive()
        if message['type'] == 'http.disconnect':
            break
        if message['type'] == 'http.request' and not message.get('more_body', False):
            break

    await send({
        'type': 'http.response.start',
        'status': 200,
        'headers': [
            (b'content-type', b'text/plain; charset=utf-8'),
            (b'trailer', b'x-trailer-one, x-trailer-two'),
        ],
    })
    await send({'type': 'http.response.body', 'body': b'ok', 'more_body': True})
    await send({
        'type': 'http.response.trailers',
        'trailers': [
            (b'x-trailer-one', b'yes'),
            (b'x-trailer-two', b'done'),
        ],
    })
