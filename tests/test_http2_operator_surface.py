from __future__ import annotations

import asyncio
import logging
import os
import unittest
from unittest.mock import patch

from tigrcorn.cli import build_parser
from tigrcorn.config.load import build_config, build_config_from_namespace
from tigrcorn.constants import H2_PREFACE
from tigrcorn.observability.logging import AccessLogger
from tigrcorn.protocols.http2.codec import (
    FRAME_PING,
    FRAME_SETTINGS,
    FRAME_WINDOW_UPDATE,
    FrameBuffer,
    HTTP2Frame,
    decode_settings,
    parse_window_update,
    serialize_settings,
)
from tigrcorn.protocols.http2.flow import next_adaptive_window_target
from tigrcorn.protocols.http2.handler import HTTP2ConnectionHandler
from tigrcorn.server.runner import TigrCornServer


async def _start_http2_server(app, *, config_mutator=None, config_payload=None):
    config = build_config(
        app=None,
        host='127.0.0.1',
        port=0,
        lifespan='off',
        http_versions=['2'],
        config=config_payload,
    )
    if config_mutator is not None:
        config_mutator(config)
    server = TigrCornServer(app, config)
    await server.start()
    port = server._listeners[0].server.sockets[0].getsockname()[1]
    return server, port


class _DummyWriter:
    def __init__(self) -> None:
        self.closed = False
        self.buffer = bytearray()

    def write(self, data: bytes) -> None:
        self.buffer.extend(data)

    async def drain(self) -> None:
        return None

    def is_closing(self) -> bool:
        return self.closed

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        return None

    def get_extra_info(self, _name: str, default=None):
        return default


async def _read_h2_frames(reader: asyncio.StreamReader, *, timeout: float = 1.0) -> list[HTTP2Frame]:
    buf = FrameBuffer()
    data = await asyncio.wait_for(reader.read(65535), timeout)
    if not data:
        return []
    buf.feed(data)
    return buf.pop_all()


class Phase4HTTP2OperatorSurfaceTests(unittest.IsolatedAsyncioTestCase):
    def test_parser_accepts_phase4_flags(self):
        parser = build_parser()
        ns = parser.parse_args(
            [
                'tests.fixtures_pkg.appmod:app',
                '--http2-max-concurrent-streams', '11',
                '--http2-max-headers-size', '12288',
                '--http2-max-frame-size', '32768',
                '--http2-adaptive-window',
                '--http2-initial-connection-window-size', '131072',
                '--http2-initial-stream-window-size', '98304',
                '--http2-keep-alive-interval', '2.5',
                '--http2-keep-alive-timeout', '1.25',
            ]
        )
        self.assertEqual(ns.http2_max_concurrent_streams, 11)
        self.assertEqual(ns.http2_max_headers_size, 12288)
        self.assertEqual(ns.http2_max_frame_size, 32768)
        self.assertTrue(ns.http2_adaptive_window)
        self.assertEqual(ns.http2_initial_connection_window_size, 131072)
        self.assertEqual(ns.http2_initial_stream_window_size, 98304)
        self.assertEqual(ns.http2_keep_alive_interval, 2.5)
        self.assertEqual(ns.http2_keep_alive_timeout, 1.25)

    def test_http2_adaptive_window_disable_form_is_respected(self):
        parser = build_parser()
        ns = parser.parse_args([
            'tests.fixtures_pkg.appmod:app',
            '--http2-adaptive-window',
            '--no-http2-adaptive-window',
        ])
        self.assertFalse(ns.http2_adaptive_window)
        config = build_config_from_namespace(ns)
        self.assertFalse(config.http.http2_adaptive_window)

    def test_build_config_from_namespace_maps_phase4_submodels(self):
        parser = build_parser()
        ns = parser.parse_args(
            [
                'tests.fixtures_pkg.appmod:app',
                '--http2-max-concurrent-streams', '7',
                '--http2-max-headers-size', '8192',
                '--http2-max-frame-size', '32768',
                '--http2-adaptive-window',
                '--http2-initial-connection-window-size', '131072',
                '--http2-initial-stream-window-size', '98304',
                '--http2-keep-alive-interval', '0.5',
                '--http2-keep-alive-timeout', '0.25',
            ]
        )
        config = build_config_from_namespace(ns)
        self.assertEqual(config.http.http2_max_concurrent_streams, 7)
        self.assertEqual(config.http.http2_max_headers_size, 8192)
        self.assertEqual(config.http.http2_max_frame_size, 32768)
        self.assertTrue(config.http.http2_adaptive_window)
        self.assertEqual(config.http.http2_initial_connection_window_size, 131072)
        self.assertEqual(config.http.http2_initial_stream_window_size, 98304)
        self.assertEqual(config.http.http2_keep_alive_interval, 0.5)
        self.assertEqual(config.http.http2_keep_alive_timeout, 0.25)

    def test_phase4_env_surface_is_respected(self):
        parser = build_parser()
        ns = parser.parse_args(['--env-prefix', 'PHASE4TEST'])
        with patch.dict(
            os.environ,
            {
                'PHASE4TEST_HTTP2_MAX_CONCURRENT_STREAMS': '13',
                'PHASE4TEST_HTTP2_MAX_HEADERS_SIZE': '9216',
                'PHASE4TEST_HTTP2_MAX_FRAME_SIZE': '32768',
                'PHASE4TEST_HTTP2_ADAPTIVE_WINDOW': 'true',
                'PHASE4TEST_HTTP2_INITIAL_CONNECTION_WINDOW_SIZE': '196608',
                'PHASE4TEST_HTTP2_INITIAL_STREAM_WINDOW_SIZE': '131072',
                'PHASE4TEST_HTTP2_KEEP_ALIVE_INTERVAL': '1.5',
                'PHASE4TEST_HTTP2_KEEP_ALIVE_TIMEOUT': '0.75',
            },
            clear=False,
        ):
            config = build_config_from_namespace(ns)
        self.assertEqual(config.http.http2_max_concurrent_streams, 13)
        self.assertEqual(config.http.http2_max_headers_size, 9216)
        self.assertEqual(config.http.http2_max_frame_size, 32768)
        self.assertTrue(config.http.http2_adaptive_window)
        self.assertEqual(config.http.http2_initial_connection_window_size, 196608)
        self.assertEqual(config.http.http2_initial_stream_window_size, 131072)
        self.assertEqual(config.http.http2_keep_alive_interval, 1.5)
        self.assertEqual(config.http.http2_keep_alive_timeout, 0.75)

    def test_generic_and_http2_specific_limits_are_coherent(self):
        fallback = build_config(
            app=None,
            http_versions=['2'],
            max_header_size=8192,
            config={'scheduler': {'max_streams': 19}},
        )
        self.assertEqual(fallback.http.http2_max_concurrent_streams, 19)
        self.assertEqual(fallback.http.http2_max_headers_size, 8192)
        self.assertEqual(fallback.http.http2_max_frame_size, 16384)

        explicit = build_config(
            app=None,
            http_versions=['2'],
            max_header_size=8192,
            http2_max_concurrent_streams=7,
            http2_max_headers_size=4096,
            http2_max_frame_size=32768,
            config={'scheduler': {'max_streams': 19}},
        )
        self.assertEqual(explicit.http.http2_max_concurrent_streams, 7)
        self.assertEqual(explicit.http.http2_max_headers_size, 4096)
        self.assertEqual(explicit.http.http2_max_frame_size, 32768)

    async def test_http2_server_advertises_configured_local_settings(self):
        async def app(scope, receive, send):
            await receive()
            await send({'type': 'http.response.start', 'status': 204, 'headers': []})
            await send({'type': 'http.response.body', 'body': b'', 'more_body': False})

        server, port = await _start_http2_server(
            app,
            config_payload={
                'http': {
                    'http2_max_concurrent_streams': 7,
                    'http2_max_headers_size': 12288,
                    'http2_max_frame_size': 32768,
                    'http2_initial_stream_window_size': 98304,
                }
            },
        )
        try:
            reader, writer = await asyncio.open_connection('127.0.0.1', port)
            writer.write(H2_PREFACE)
            writer.write(serialize_settings({}))
            await writer.drain()
            settings_payload = None
            deadline = asyncio.get_running_loop().time() + 1.0
            while settings_payload is None and asyncio.get_running_loop().time() < deadline:
                for frame in await _read_h2_frames(reader):
                    if frame.frame_type == FRAME_SETTINGS and frame.payload:
                        settings_payload = decode_settings(frame.payload)
                        break
            self.assertIsNotNone(settings_payload)
            assert settings_payload is not None
            self.assertEqual(settings_payload[0x3], 7)
            self.assertEqual(settings_payload[0x6], 12288)
            self.assertEqual(settings_payload[0x5], 32768)
            self.assertEqual(settings_payload[0x4], 98304)
            writer.close()
            await writer.wait_closed()
        finally:
            await server.close()

    async def test_http2_initial_connection_window_emits_stream_zero_window_update(self):
        async def app(scope, receive, send):
            await receive()
            await send({'type': 'http.response.start', 'status': 204, 'headers': []})
            await send({'type': 'http.response.body', 'body': b'', 'more_body': False})

        target = 131072
        server, port = await _start_http2_server(
            app,
            config_payload={'http': {'http2_initial_connection_window_size': target}},
        )
        try:
            reader, writer = await asyncio.open_connection('127.0.0.1', port)
            writer.write(H2_PREFACE)
            writer.write(serialize_settings({}))
            await writer.drain()
            increment = None
            deadline = asyncio.get_running_loop().time() + 1.0
            while increment is None and asyncio.get_running_loop().time() < deadline:
                for frame in await _read_h2_frames(reader):
                    if frame.frame_type == FRAME_WINDOW_UPDATE and frame.stream_id == 0:
                        increment = parse_window_update(frame.payload)
                        break
            self.assertEqual(increment, target - 65535)
            writer.close()
            await writer.wait_closed()
        finally:
            await server.close()

    async def test_http2_adaptive_window_growth_emits_window_updates(self):
        async def app(scope, receive, send):
            await send({'type': 'http.response.start', 'status': 204, 'headers': []})
            await send({'type': 'http.response.body', 'body': b'', 'more_body': False})

        config = build_config(app=None, http_versions=['2'], config={'http': {'http2_adaptive_window': True}})
        handler = HTTP2ConnectionHandler(
            app=app,
            config=config,
            access_logger=AccessLogger(logging.getLogger('phase4-h2-test')),
            reader=asyncio.StreamReader(),
            writer=_DummyWriter(),
            client=None,
            server=None,
            scheme='http',
        )
        updates: list[bytes] = []

        async def capture_write(data: bytes, *, record_activity: bool = True) -> None:
            updates.append(data)

        handler._write_raw = capture_write  # type: ignore[method-assign]
        state = handler.streams.activate_remote(
            1,
            send_window=handler.state.initial_window_size,
            receive_window=handler.state.local_initial_window_size,
        )
        self.assertEqual(next_adaptive_window_target(65535, 40000), 131070)
        handler.state.connection_receive_window.consume(40000)
        state.receive_window.consume(40000)
        await handler._maybe_replenish_receive_credit(1, 40000)
        self.assertGreater(handler.state.connection_receive_window_target, 65535)
        self.assertGreater(state.receive_window_target, 65535)
        buf = FrameBuffer()
        for payload in updates:
            buf.feed(payload)
        frames = buf.pop_all()
        window_updates = [frame for frame in frames if frame.frame_type == FRAME_WINDOW_UPDATE]
        self.assertEqual({frame.stream_id for frame in window_updates}, {0, 1})
        self.assertTrue(all(parse_window_update(frame.payload) > 0 for frame in window_updates))

    async def test_http2_keepalive_sends_ping_then_closes_on_timeout(self):
        async def app(scope, receive, send):
            await send({'type': 'http.response.start', 'status': 204, 'headers': []})
            await send({'type': 'http.response.body', 'body': b'', 'more_body': False})

        server, port = await _start_http2_server(
            app,
            config_payload={'http': {'http2_keep_alive_interval': 0.05, 'http2_keep_alive_timeout': 0.05}},
        )
        try:
            reader, writer = await asyncio.open_connection('127.0.0.1', port)
            writer.write(H2_PREFACE)
            writer.write(serialize_settings({}))
            await writer.drain()
            saw_ping = False
            deadline = asyncio.get_running_loop().time() + 1.0
            while not saw_ping and asyncio.get_running_loop().time() < deadline:
                frames = await _read_h2_frames(reader)
                if not frames:
                    break
                saw_ping = any(frame.frame_type == FRAME_PING for frame in frames)
            self.assertTrue(saw_ping)
            tail = await asyncio.wait_for(reader.read(), 1.0)
            self.assertEqual(tail, b'')
            writer.close()
            await writer.wait_closed()
        finally:
            await server.close()


if __name__ == '__main__':
    unittest.main()
