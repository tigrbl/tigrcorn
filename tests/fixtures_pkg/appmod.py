async def app(scope, receive, send):
    if scope['type'] == 'lifespan':
        message = await receive()
        if message['type'] == 'lifespan.startup':
            await send({'type': 'lifespan.startup.complete'})
        elif message['type'] == 'lifespan.shutdown':
            await send({'type': 'lifespan.shutdown.complete'})
        return
    if scope['type'] == 'http':
        message = await receive()
        await send({'type': 'http.response.start', 'status': 200, 'headers': [(b'content-type', b'text/plain')]})
        await send({'type': 'http.response.body', 'body': message.get('body', b''), 'more_body': False})
        return
    if scope['type'] == 'tigrcorn.rawframed':
        message = await receive()
        await send({'type': 'tigrcorn.stream.send', 'data': message['data'][::-1], 'more_data': False})
        return
    if scope['type'] == 'tigrcorn.quic':
        message = await receive()
        await send({'type': 'tigrcorn.stream.send', 'data': message['data'][::-1], 'more_data': False})
        return
    raise RuntimeError(f'unhandled scope type: {scope["type"]}')


def factory():
    return app
