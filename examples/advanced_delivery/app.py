from __future__ import annotations

from pathlib import Path

from tigrcorn.static import StaticFilesApp


ROOT = Path(__file__).parent / 'public'
STATIC_APP = StaticFilesApp(ROOT)


async def app(scope, receive, send):
    scope_type = scope['type']
    if scope_type == 'lifespan':
        while True:
            message = await receive()
            if message['type'] == 'lifespan.startup':
                await send({'type': 'lifespan.startup.complete'})
            elif message['type'] == 'lifespan.shutdown':
                await send({'type': 'lifespan.shutdown.complete'})
                return
        
    if scope_type != 'http':
        raise RuntimeError('advanced delivery example only serves HTTP')

    await receive()
    path = scope.get('path', '/')
    if path.startswith('/static/'):
        static_scope = dict(scope)
        static_scope['path'] = path.removeprefix('/static') or '/'
        await STATIC_APP(static_scope, receive, send)
        return

    if path == '/early-hints':
        await send(
            {
                'type': 'http.response.start',
                'status': 103,
                'headers': [
                    (b'link', b'</static/app.js>; rel=preload; as=script'),
                    (b'x-ignored', b'should-not-appear-in-103'),
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
        await send({'type': 'http.response.body', 'body': b'advanced delivery ok', 'more_body': False})
        return

    if path == '/alt-svc':
        await send(
            {
                'type': 'http.response.start',
                'status': 200,
                'headers': [(b'content-type', b'text/plain; charset=utf-8')],
            }
        )
        await send({'type': 'http.response.body', 'body': b'alt-svc ready', 'more_body': False})
        return

    await send(
        {
            'type': 'http.response.start',
            'status': 200,
            'headers': [(b'content-type', b'text/html; charset=utf-8')],
        }
    )
    await send({'type': 'http.response.body', 'body': (ROOT / 'index.html').read_bytes(), 'more_body': False})
