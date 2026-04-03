
from tigrcorn.config.model import ListenerConfig, ServerConfig
from tigrcorn.observability.logging import AccessLogger, configure_logging
from tigrcorn.protocols.rawframed.frames import encode_frame
from tigrcorn.protocols.rawframed.handler import RawFramedApplicationHandler


import pytest
class _FakeConnection:
    def __init__(self):
        self.writes = bytearray()

    def write(self, data: bytes) -> int:
        self.writes.extend(data)
        return len(data)



async def test_frame_dispatch():
    async def app(scope, receive, send):
        assert scope['type'] == 'tigrcorn.rawframed'
        event = await receive()
        assert event['data'] == b'abcdef'
        await send({'type': 'tigrcorn.stream.send', 'data': b'fedcba', 'more_data': False})

    handler = RawFramedApplicationHandler(
        app=app,
        config=ServerConfig(),
        listener=ListenerConfig(kind='pipe', path='/tmp/test.pipe'),
        access_logger=AccessLogger(configure_logging('warning'), enabled=False),
    )
    conn = _FakeConnection()
    await handler.feed_bytes(conn, encode_frame(b'abcdef'))
    assert bytes(conn.writes) == encode_frame(b'fedcba')