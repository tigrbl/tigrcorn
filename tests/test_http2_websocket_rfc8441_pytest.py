import asyncio

from tigrcorn.config.load import build_config
from tigrcorn.constants import H2_PREFACE
from tigrcorn.protocols.http2.codec import FRAME_DATA, FRAME_HEADERS, FRAME_SETTINGS, FrameBuffer, FrameWriter, decode_settings, serialize_settings
from tigrcorn.protocols.http2.hpack import decode_header_block, encode_header_block
from tigrcorn.protocols.websocket.frames import encode_frame, parse_frame_bytes
from tigrcorn.server.runner import TigrCornServer


import pytest
async def _start_server(app):
    config = build_config(host='127.0.0.1', port=0, lifespan='off', http_versions=['2'])
    server = TigrCornServer(app, config)
    await server.start()
    port = server._listeners[0].server.sockets[0].getsockname()[1]
    return server, port



async def test_extended_connect_websocket_roundtrip():
    seen = {}

    async def app(scope, receive, send):
        assert scope['type'] == 'websocket'
        assert scope['http_version'] == '2'
        connect = await receive()
        assert connect['type'] == 'websocket.connect'
        await send({'type': 'websocket.accept', 'subprotocol': 'chat', 'headers': []})
        event = await receive()
        seen['text'] = event['text']
        await send({'type': 'websocket.send', 'text': event['text']})
        await send({'type': 'websocket.close', 'code': 1000})

    server, port = await _start_server(app)
    try:
        reader, writer = await asyncio.open_connection('127.0.0.1', port)
        frame_writer = FrameWriter()
        writer.write(H2_PREFACE)
        writer.write(serialize_settings({}))
        header_block = encode_header_block([
            (b':method', b'CONNECT'),
            (b':protocol', b'websocket'),
            (b':scheme', b'http'),
            (b':path', b'/chat'),
            (b':authority', b'example'),
            (b'sec-websocket-version', b'13'),
            (b'sec-websocket-protocol', b'chat'),
        ])
        writer.write(frame_writer.headers(1, header_block, end_stream=False))
        writer.write(frame_writer.data(1, encode_frame(0x1, b'hello-h2-ws', masked=True), end_stream=False))
        await writer.drain()

        buf = FrameBuffer()
        response_headers = []
        ws_data = bytearray()
        end_stream = False
        while not end_stream:
            data = await asyncio.wait_for(reader.read(65535), 2.0)
            assert data
            buf.feed(data)
            for frame in buf.pop_all():
                if frame.frame_type == FRAME_SETTINGS:
                    if frame.payload:
                        decode_settings(frame.payload)
                elif frame.frame_type == FRAME_HEADERS:
                    response_headers.extend(decode_header_block(frame.payload))
                    if frame.flags & 0x1:
                        end_stream = True
                elif frame.frame_type == FRAME_DATA:
                    ws_data.extend(frame.payload)
                    if frame.flags & 0x1:
                        end_stream = True
            if response_headers and ws_data and end_stream:
                break

        assert (b':status' in b'200'), response_headers
        assert (b'sec-websocket-protocol' in b'chat'), response_headers
        frame = parse_frame_bytes(bytes(ws_data), expect_masked=False)
        assert frame.payload.decode('utf-8') == 'hello-h2-ws'
        assert seen['text'] == 'hello-h2-ws'
        writer.close()
        await writer.wait_closed()
    finally:
        await server.close()
