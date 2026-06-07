from __future__ import annotations

import asyncio
import base64
import os
import socket
import unittest
from contextlib import suppress

from tigrcorn.config.load import build_config
from tigrcorn.constants import H2_PREFACE
from tigrcorn.protocols.http2.codec import FRAME_DATA, FRAME_HEADERS, FRAME_SETTINGS, FrameBuffer, FrameWriter, decode_settings, serialize_settings
from tigrcorn.protocols.http2.hpack import decode_header_block, encode_header_block
from tigrcorn.protocols.http3 import HTTP3ConnectionCore
from tigrcorn.protocols.http3.codec import SETTING_ENABLE_CONNECT_PROTOCOL
from tigrcorn.protocols.websocket.frames import decode_close_payload, encode_frame, parse_frame_bytes, read_frame
from tigrcorn.scheduler import ProductionScheduler, SchedulerPolicy
from tigrcorn.server.runner import TigrCornServer
from tigrcorn.transports.quic import QuicConnection


def _frame_wire_length(data: bytes) -> int:
    if len(data) < 2:
        raise AssertionError('websocket frame is truncated')
    masked = bool(data[1] & 0x80)
    length = data[1] & 0x7F
    pos = 2
    if length == 126:
        if len(data) < pos + 2:
            raise AssertionError('websocket frame is truncated')
        length = int.from_bytes(data[pos:pos + 2], 'big')
        pos += 2
    elif length == 127:
        if len(data) < pos + 8:
            raise AssertionError('websocket frame is truncated')
        length = int.from_bytes(data[pos:pos + 8], 'big')
        pos += 8
    if masked:
        pos += 4
    total = pos + length
    if len(data) < total:
        raise AssertionError('websocket frame is truncated')
    return total


async def _start_server(app, *, http_versions: list[str], transport: str = 'tcp', scheduler: dict | None = None, websocket: dict | None = None, protocols: list[str] | None = None):
    payload = {}
    if scheduler is not None:
        payload['scheduler'] = scheduler
    if websocket is not None:
        payload['websocket'] = websocket
    kwargs = {
        'host': '127.0.0.1',
        'port': 0,
        'lifespan': 'off',
        'http_versions': http_versions,
        'config': payload or None,
    }
    if transport == 'udp':
        kwargs.update({'transport': 'udp', 'protocols': protocols or ['http3'], 'quic_secret': b'shared'})
    config = build_config(**kwargs)
    server = TigrCornServer(app, config)
    await server.start()
    if transport == 'udp':
        port = server._listeners[0].transport.get_extra_info('sockname')[1]
    else:
        port = server._listeners[0].server.sockets[0].getsockname()[1]
    return server, port


