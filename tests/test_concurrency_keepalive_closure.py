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


class Phase9F3ConcurrencyKeepaliveClosureTests(unittest.IsolatedAsyncioTestCase):
    async def test_scheduler_limit_concurrency_is_real_global_inflight_cap(self):
        scheduler = ProductionScheduler(SchedulerPolicy(limit_concurrency=1))
        first = scheduler.acquire_work()
        self.assertIsNotNone(first)
        assert first is not None
        self.assertEqual(scheduler.current_inflight, 1)
        self.assertIsNone(scheduler.acquire_work())
        first.release()
        self.assertEqual(scheduler.current_inflight, 0)

        gate = asyncio.Event()

        async def sleeper():
            await gate.wait()

        task = scheduler.spawn(sleeper())
        await asyncio.sleep(0)
        self.assertEqual(scheduler.current_inflight, 1)
        with self.assertRaises(RuntimeError):
            scheduler.spawn(asyncio.sleep(0))
        gate.set()
        await task
        self.assertEqual(scheduler.current_inflight, 0)
        await scheduler.close()

    async def test_http11_limit_concurrency_returns_503_on_second_request(self):
        release = asyncio.Event()
        started = asyncio.Event()

        async def app(scope, receive, send):
            if scope['type'] != 'http':
                return
            if scope['path'] == '/hold':
                started.set()
                await release.wait()
            await send({'type': 'http.response.start', 'status': 200, 'headers': []})
            await send({'type': 'http.response.body', 'body': b'ok', 'more_body': False})

        server, port = await _start_server(app, http_versions=['1.1'], scheduler={'limit_concurrency': 1})
        try:
            r1, w1 = await asyncio.open_connection('127.0.0.1', port)
            w1.write(b'GET /hold HTTP/1.1\r\nHost: localhost\r\nConnection: keep-alive\r\n\r\n')
            await w1.drain()
            await asyncio.wait_for(started.wait(), 1.0)

            r2, w2 = await asyncio.open_connection('127.0.0.1', port)
            w2.write(b'GET /next HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n')
            await w2.drain()
            response = await asyncio.wait_for(r2.readuntil(b'\r\n\r\n'), 1.0)
            self.assertIn(b'503', response)
            self.assertIn(b'scheduler overloaded', await asyncio.wait_for(r2.read(), 1.0))
            self.assertGreaterEqual(server.state.metrics.scheduler_rejections, 1)

            release.set()
            data = await asyncio.wait_for(r1.readuntil(b'\r\n\r\n'), 1.0)
            self.assertIn(b'200', data)
            w1.close(); w2.close()
            await w1.wait_closed(); await w2.wait_closed()
        finally:
            release.set()
            await server.close()

    async def test_http2_limit_concurrency_returns_503_on_second_stream(self):
        release = asyncio.Event()
        started = asyncio.Event()

        async def app(scope, receive, send):
            if scope['type'] != 'http':
                return
            if scope['path'] == '/hold':
                started.set()
                await release.wait()
            await send({'type': 'http.response.start', 'status': 200, 'headers': []})
            await send({'type': 'http.response.body', 'body': b'ok', 'more_body': False})

        server, port = await _start_server(app, http_versions=['2'], scheduler={'limit_concurrency': 1})
        try:
            reader, writer = await asyncio.open_connection('127.0.0.1', port)
            frame_writer = FrameWriter()
            writer.write(H2_PREFACE)
            writer.write(serialize_settings({}))
            hold_headers = encode_header_block([
                (b':method', b'GET'),
                (b':scheme', b'http'),
                (b':path', b'/hold'),
                (b':authority', b'example'),
            ])
            next_headers = encode_header_block([
                (b':method', b'GET'),
                (b':scheme', b'http'),
                (b':path', b'/next'),
                (b':authority', b'example'),
            ])
            writer.write(frame_writer.headers(1, hold_headers, end_stream=True))
            await writer.drain()
            await asyncio.wait_for(started.wait(), 1.0)
            writer.write(frame_writer.headers(3, next_headers, end_stream=True))
            await writer.drain()

            buf = FrameBuffer()
            statuses: dict[int, bytes] = {}
            bodies: dict[int, bytearray] = {1: bytearray(), 3: bytearray()}
            while 3 not in statuses:
                data = await asyncio.wait_for(reader.read(65535), 1.0)
                self.assertTrue(data)
                buf.feed(data)
                for frame in buf.pop_all():
                    if frame.frame_type == FRAME_SETTINGS and frame.payload:
                        decode_settings(frame.payload)
                    elif frame.frame_type == FRAME_HEADERS:
                        header_map = dict(decode_header_block(frame.payload))
                        statuses[frame.stream_id] = header_map.get(b':status', b'0')
                    elif frame.frame_type == FRAME_DATA:
                        bodies.setdefault(frame.stream_id, bytearray()).extend(frame.payload)
            self.assertEqual(statuses[3], b'503')
            self.assertIn(b'scheduler overloaded', bytes(bodies[3]))
            self.assertGreaterEqual(server.state.metrics.scheduler_rejections, 1)
            release.set()
            writer.close()
            await writer.wait_closed()
        finally:
            release.set()
            await server.close()

    async def test_http3_websocket_admission_returns_503_when_limit_reached(self):
        async def app(scope, receive, send):
            if scope['type'] != 'websocket':
                return
            event = await receive()
            self.assertEqual(event['type'], 'websocket.connect')
            await send({'type': 'websocket.accept', 'headers': []})
            await asyncio.sleep(0.25)

        server, port = await _start_server(
            app,
            http_versions=['3'],
            transport='udp',
            protocols=['http3'],
            scheduler={'limit_concurrency': 1},
        )
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setblocking(False)
        client = QuicConnection(is_client=True, secret=b'shared', local_cid=b'cli-admit')
        core = HTTP3ConnectionCore()
        loop = asyncio.get_running_loop()
        try:
            sock.sendto(client.build_initial(), ('127.0.0.1', port))
            for _ in range(4):
                data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 1.0)
                for event in client.receive_datagram(data):
                    if event.kind == 'stream':
                        core.receive_stream_data(event.stream_id, event.data, fin=event.fin)
                if core.state.remote_settings.get(SETTING_ENABLE_CONNECT_PROTOCOL) == 1:
                    break

            payload1 = core.get_request(0).encode_request([
                (b':method', b'CONNECT'),
                (b':protocol', b'websocket'),
                (b':scheme', b'https'),
                (b':path', b'/ws1'),
                (b':authority', b'example'),
                (b'sec-websocket-version', b'13'),
            ], b'')
            sock.sendto(client.send_stream_data(0, payload1, fin=False), ('127.0.0.1', port))

            first_response = None
            for _ in range(10):
                data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 1.0)
                for event in client.receive_datagram(data):
                    if event.kind == 'stream':
                        state = core.receive_stream_data(event.stream_id, event.data, fin=event.fin)
                        if event.stream_id == 0 and state.headers:
                            first_response = state
                if first_response is not None:
                    break
            self.assertIsNotNone(first_response)
            assert first_response is not None
            self.assertIn((b':status', b'200'), first_response.headers)

            payload2 = core.get_request(4).encode_request([
                (b':method', b'CONNECT'),
                (b':protocol', b'websocket'),
                (b':scheme', b'https'),
                (b':path', b'/ws2'),
                (b':authority', b'example'),
                (b'sec-websocket-version', b'13'),
            ], b'')
            sock.sendto(client.send_stream_data(4, payload2, fin=True), ('127.0.0.1', port))

            second_response = None
            for _ in range(10):
                data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 1.0)
                for event in client.receive_datagram(data):
                    if event.kind == 'stream':
                        state = core.receive_stream_data(event.stream_id, event.data, fin=event.fin)
                        if event.stream_id == 4 and state.headers:
                            second_response = state
                if second_response is not None and second_response.ended:
                    break
            self.assertIsNotNone(second_response)
            assert second_response is not None
            self.assertIn((b':status', b'503'), second_response.headers)
            self.assertEqual(second_response.body, b'scheduler overloaded')
            self.assertGreaterEqual(server.state.metrics.scheduler_rejections, 1)
        finally:
            sock.close()
            await server.close()

    async def test_http11_websocket_keepalive_sends_ping_then_closes_on_timeout(self):
        async def app(scope, receive, send):
            if scope['type'] != 'websocket':
                return
            connect = await receive()
            self.assertEqual(connect['type'], 'websocket.connect')
            await send({'type': 'websocket.accept', 'headers': []})
            await asyncio.sleep(0.25)

        server, port = await _start_server(app, http_versions=['1.1'], websocket={'ping_interval': 0.05, 'ping_timeout': 0.05})
        try:
            reader, writer = await asyncio.open_connection('127.0.0.1', port)
            key = base64.b64encode(os.urandom(16))
            request = (
                b'GET /ws HTTP/1.1\r\n'
                b'Host: localhost\r\n'
                b'Upgrade: websocket\r\n'
                b'Connection: Upgrade\r\n'
                b'Sec-WebSocket-Version: 13\r\n'
                b'Sec-WebSocket-Key: ' + key + b'\r\n\r\n'
            )
            writer.write(request)
            await writer.drain()
            response = await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'), 1.0)
            self.assertIn(b'101 Switching Protocols', response)
            ping = await read_frame(reader, max_payload_size=1024, expect_masked=False)
            close = await read_frame(reader, max_payload_size=1024, expect_masked=False)
            self.assertEqual(ping.opcode, 0x9)
            self.assertEqual(close.opcode, 0x8)
            code, reason = decode_close_payload(close.payload)
            self.assertEqual(code, 1011)
            self.assertEqual(reason, 'ping timeout')
            self.assertGreaterEqual(server.state.metrics.websocket_pings_sent, 1)
            self.assertGreaterEqual(server.state.metrics.websocket_ping_timeouts, 1)
            writer.close()
            await writer.wait_closed()
        finally:
            await server.close()

    async def test_http2_websocket_keepalive_sends_ping_then_closes_on_timeout(self):
        async def app(scope, receive, send):
            if scope['type'] != 'websocket':
                return
            connect = await receive()
            self.assertEqual(connect['type'], 'websocket.connect')
            await send({'type': 'websocket.accept', 'headers': []})
            await asyncio.sleep(0.25)

        server, port = await _start_server(app, http_versions=['2'], websocket={'ping_interval': 0.05, 'ping_timeout': 0.05})
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
            ])
            writer.write(frame_writer.headers(1, header_block, end_stream=False))
            await writer.drain()

            buf = FrameBuffer()
            response_headers = []
            ws_data = bytearray()
            end_stream = False
            while not end_stream:
                data = await asyncio.wait_for(reader.read(65535), 2.0)
                self.assertTrue(data)
                buf.feed(data)
                for frame in buf.pop_all():
                    if frame.frame_type == FRAME_SETTINGS and frame.payload:
                        decode_settings(frame.payload)
                    elif frame.frame_type == FRAME_HEADERS:
                        response_headers.extend(decode_header_block(frame.payload))
                        if frame.flags & 0x1:
                            end_stream = True
                    elif frame.frame_type == FRAME_DATA:
                        ws_data.extend(frame.payload)
                        if frame.flags & 0x1:
                            end_stream = True
                if response_headers and end_stream:
                    break
            self.assertIn((b':status', b'200'), response_headers)
            first_len = _frame_wire_length(bytes(ws_data))
            ping = parse_frame_bytes(bytes(ws_data[:first_len]), expect_masked=False)
            close = parse_frame_bytes(bytes(ws_data[first_len:]), expect_masked=False)
            self.assertEqual(ping.opcode, 0x9)
            code, reason = decode_close_payload(close.payload)
            self.assertEqual(code, 1011)
            self.assertEqual(reason, 'ping timeout')
            self.assertGreaterEqual(server.state.metrics.websocket_pings_sent, 1)
            self.assertGreaterEqual(server.state.metrics.websocket_ping_timeouts, 1)
            writer.close()
            await writer.wait_closed()
        finally:
            await server.close()

    async def test_http3_websocket_keepalive_sends_ping_then_closes_on_timeout(self):
        async def app(scope, receive, send):
            if scope['type'] != 'websocket':
                return
            connect = await receive()
            self.assertEqual(connect['type'], 'websocket.connect')
            await send({'type': 'websocket.accept', 'headers': []})
            await asyncio.sleep(0.25)

        server, port = await _start_server(app, http_versions=['3'], transport='udp', protocols=['http3'], websocket={'ping_interval': 0.05, 'ping_timeout': 0.05})
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setblocking(False)
        client = QuicConnection(is_client=True, secret=b'shared', local_cid=b'cli-keep')
        core = HTTP3ConnectionCore()
        loop = asyncio.get_running_loop()
        try:
            sock.sendto(client.build_initial(), ('127.0.0.1', port))
            for _ in range(4):
                data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 1.0)
                for event in client.receive_datagram(data):
                    if event.kind == 'stream':
                        core.receive_stream_data(event.stream_id, event.data, fin=event.fin)
                if core.state.remote_settings.get(SETTING_ENABLE_CONNECT_PROTOCOL) == 1:
                    break

            payload = core.get_request(0).encode_request([
                (b':method', b'CONNECT'),
                (b':protocol', b'websocket'),
                (b':scheme', b'https'),
                (b':path', b'/chat'),
                (b':authority', b'example'),
                (b'sec-websocket-version', b'13'),
            ], b'')
            sock.sendto(client.send_stream_data(0, payload, fin=False), ('127.0.0.1', port))
            response_state = None
            for _ in range(10):
                data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 1.0)
                for event in client.receive_datagram(data):
                    if event.kind == 'stream':
                        response_state = core.receive_stream_data(event.stream_id, event.data, fin=event.fin)
                if response_state is not None and response_state.ended:
                    break
            self.assertIsNotNone(response_state)
            assert response_state is not None
            self.assertIn((b':status', b'200'), response_state.headers)
            first_len = _frame_wire_length(response_state.body)
            ping = parse_frame_bytes(response_state.body[:first_len], expect_masked=False)
            close = parse_frame_bytes(response_state.body[first_len:], expect_masked=False)
            self.assertEqual(ping.opcode, 0x9)
            code, reason = decode_close_payload(close.payload)
            self.assertEqual(code, 1011)
            self.assertEqual(reason, 'ping timeout')
            self.assertGreaterEqual(server.state.metrics.websocket_pings_sent, 1)
            self.assertGreaterEqual(server.state.metrics.websocket_ping_timeouts, 1)
        finally:
            sock.close()
            await server.close()


if __name__ == '__main__':
    unittest.main()
