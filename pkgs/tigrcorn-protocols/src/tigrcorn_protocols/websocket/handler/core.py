from __future__ import annotations

import asyncio
from contextlib import suppress

from tigrcorn_asgi.events.websocket import (
    websocket_connect,
    websocket_disconnect,
    websocket_receive_bytes,
    websocket_receive_text,
)
from tigrcorn_asgi.receive import QueueReceive
from tigrcorn_asgi.scopes.websocket import build_websocket_scope
from tigrcorn_config.model import ServerConfig
from tigrcorn_core.errors import ProtocolError
from tigrcorn_core.types import ASGIApp
from tigrcorn_observability.logging import AccessLogger
from tigrcorn_observability.metrics import Metrics
from tigrcorn_protocols.flow.keepalive import KeepAlivePolicy, KeepAliveRuntime
from tigrcorn_protocols.http1.serializer import serialize_http11_response_whole
from tigrcorn_protocols.websocket.codec import close_frame, pong_frame
from tigrcorn_protocols.websocket.extensions import parse_permessage_deflate_offers
from tigrcorn_protocols.websocket.frames import (
    OP_BINARY,
    OP_CLOSE,
    OP_CONT,
    OP_PING,
    OP_PONG,
    OP_TEXT,
    decode_close_payload,
    read_frame,
    serialize_frame,
)
from tigrcorn_protocols.websocket.handshake import validate_client_handshake

from .app_send import _WSAppSend
from .errors import _WebSocketCloseSignal


class WebSocketConnectionHandler:
    def __init__(
        self,
        *,
        app: ASGIApp,
        config: ServerConfig,
        access_logger: AccessLogger,
        request,
        reader,
        writer,
        client,
        server,
        scheme: str,
        scope_extensions: dict | None = None,
        metrics: Metrics | None = None,
    ) -> None:
        self.app = app
        self.config = config
        self.access_logger = access_logger
        self.request = request
        self.reader = reader
        self.writer = writer
        self.client = client
        self.server = server
        self.scheme = scheme
        self.scope_extensions = dict(scope_extensions or {})
        self.metrics = metrics
        self.receive = QueueReceive(max_size=self.config.websocket.max_queue)
        self.accepted = asyncio.Event()
        self.write_lock = asyncio.Lock()
        self.keepalive_policy = KeepAlivePolicy(
            idle_timeout=self.config.http.idle_timeout,
            ping_interval=self.config.websocket.ping_interval,
            ping_timeout=self.config.websocket.ping_timeout,
        )
        self.keepalive = KeepAliveRuntime(self.keepalive_policy) if self.keepalive_policy.enabled else None
        self.keepalive_task: asyncio.Task[None] | None = None
        self.state = {
            'accepted': False,
            'closed': False,
            'http_denied': False,
            'http_denial_status': 403,
            'http_denial_headers': [],
            'http_denial_started': False,
            'sec_websocket_key': validate_client_handshake(request.headers),
            'request_headers': request.headers,
            'permessage_deflate_offers': parse_permessage_deflate_offers(request.headers),
            'permessage_deflate_runtime': None,
        }
        self.send = _WSAppSend(
            writer=writer,
            server_header=config.server_header_value,
            state=self.state,
            accepted=self.accepted,
            allowed_subprotocols=self._scope()['subprotocols'],
            include_date_header=config.include_date_header,
            default_headers=list(config.default_response_headers),
            config=config,
            write_lock=self.write_lock,
            keepalive=self.keepalive,
        )

    def _scope(self) -> dict:
        return build_websocket_scope(
            self.request,
            client=self.client,
            server=self.server,
            scheme=self.scheme,
            extensions=self.scope_extensions,
            root_path=self.config.proxy.root_path,
            proxy=self.config.proxy,
        )

    async def handle(self) -> None:
        scope = self._scope()
        self.send.allowed_subprotocols = scope['subprotocols']
        await self.receive.put(websocket_connect())
        reader_task = asyncio.create_task(self._frame_reader(), name='tigrcorn-ws-reader')
        if self.keepalive is not None:
            self.keepalive_task = asyncio.create_task(self._keepalive_loop(), name='tigrcorn-ws-keepalive')
        try:
            await self.app(scope, self.receive, self.send)
        except Exception:
            if self.state['accepted'] and not self.state['closed']:
                with suppress(Exception):
                    await self._write(close_frame(1011, 'internal error'))
            raise
        finally:
            await self._finalize(reader_task)

    async def _finalize(self, reader_task: asyncio.Task) -> None:
        if not self.state['accepted'] and not self.state['http_denied']:
            await self._write(
                serialize_http11_response_whole(
                    status=403,
                    headers=[],
                    body=b'',
                    keep_alive=False,
                    server_header=self.config.server_header_value,
                    include_date_header=self.config.include_date_header,
                    default_headers=self.config.default_response_headers,
                )
            )
            self.state['closed'] = True
        elif self.state['http_denied'] and not self.state['http_denial_started']:
            await self._write(
                serialize_http11_response_whole(
                    status=self.state['http_denial_status'],
                    headers=self.state['http_denial_headers'],
                    body=b'',
                    keep_alive=False,
                    server_header=self.config.server_header_value,
                    include_date_header=self.config.include_date_header,
                    default_headers=self.config.default_response_headers,
                )
            )
            self.state['closed'] = True
        elif self.state['accepted'] and not self.state['closed']:
            await self._write(close_frame(1000, ''))
            self.state['closed'] = True
        if self.keepalive_task is not None:
            self.keepalive_task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await self.keepalive_task
        reader_task.cancel()
        with suppress(asyncio.CancelledError, Exception):
            await reader_task
        self.access_logger.log_ws(self.client, self.request.path, 'accepted' if self.state['accepted'] else 'denied')

    async def _write(self, data: bytes) -> None:
        async with self.write_lock:
            self.writer.write(data)
            await self.writer.drain()

    def _record_activity(self) -> None:
        if self.keepalive is not None:
            self.keepalive.record_activity()

    async def _keepalive_loop(self) -> None:
        await self.accepted.wait()
        while not self.state['closed']:
            await asyncio.sleep(0.05)
            if self.keepalive is None or self.state['closed']:
                return
            if self.keepalive.ping_timed_out():
                if self.metrics is not None:
                    self.metrics.websocket_ping_timeout()
                await self._fail_connection(1011, 'ping timeout')
                return
            payload = self.keepalive.next_ping_payload()
            if payload is None:
                continue
            if self.metrics is not None:
                self.metrics.websocket_ping_sent()
            await self._write(serialize_frame(OP_PING, payload))

    def _ensure_message_size(self, size: int) -> None:
        if size > self.config.websocket_max_message_size:
            raise _WebSocketCloseSignal(1009, 'message too big')

    async def _fail_connection(self, code: int, reason: str) -> None:
        if not self.state['closed']:
            await self._write(close_frame(code, reason))
        await self.receive.put(websocket_disconnect(code, reason))
        self.state['closed'] = True

    async def _frame_reader(self) -> None:
        await self.accepted.wait()
        fragmented_opcode: int | None = None
        fragments: list[bytes] = []
        fragmented_compressed = False
        current_message_size = 0
        while not self.state['closed']:
            try:
                frame = await read_frame(
                    self.reader,
                    max_payload_size=self.config.websocket_max_message_size,
                    allow_rsv1=self.state.get('permessage_deflate_runtime') is not None,
                )
                self._record_activity()
                fragmented_opcode, fragments, fragmented_compressed, current_message_size = await self._handle_frame(
                    frame,
                    fragmented_opcode,
                    fragments,
                    fragmented_compressed,
                    current_message_size,
                )
            except asyncio.CancelledError:
                raise
            except _WebSocketCloseSignal as exc:
                await self._fail_connection(exc.code, exc.reason)
                return
            except ProtocolError:
                await self._fail_connection(1002, 'protocol error')
                return
            except Exception:
                await self.receive.put(websocket_disconnect(1006, ''))
                self.state['closed'] = True
                return

    async def _handle_frame(
        self,
        frame,
        fragmented_opcode: int | None,
        fragments: list[bytes],
        fragmented_compressed: bool,
        current_message_size: int,
    ) -> tuple[int | None, list[bytes], bool, int]:
        if frame.opcode == OP_PING:
            await self._write(pong_frame(frame.payload))
            return fragmented_opcode, fragments, fragmented_compressed, current_message_size
        if frame.opcode == OP_PONG:
            if self.keepalive is not None:
                self.keepalive.acknowledge_pong(frame.payload)
            return fragmented_opcode, fragments, fragmented_compressed, current_message_size
        if frame.opcode == OP_CLOSE:
            code, reason = decode_close_payload(frame.payload)
            if not self.state['closed']:
                await self._write(close_frame(code, reason))
            self.state['closed'] = True
            await self.receive.put(websocket_disconnect(code, reason))
            return fragmented_opcode, fragments, fragmented_compressed, current_message_size
        if frame.opcode in {OP_TEXT, OP_BINARY}:
            return await self._handle_data_frame(frame, fragmented_opcode)
        if frame.opcode == OP_CONT:
            return await self._handle_continuation_frame(frame, fragmented_opcode, fragments, fragmented_compressed, current_message_size)
        raise ProtocolError('unsupported websocket opcode')

    async def _handle_data_frame(self, frame, fragmented_opcode: int | None) -> tuple[int | None, list[bytes], bool, int]:
        if fragmented_opcode is not None:
            raise ProtocolError('new data frame before fragmented message completion')
        current_message_size = len(frame.payload)
        self._ensure_message_size(current_message_size)
        if frame.fin:
            runtime = self.state.get('permessage_deflate_runtime')
            payload = runtime.decompress_message(frame.payload) if frame.rsv1 and runtime is not None else frame.payload
            await self._deliver_message(frame.opcode, payload)
            return None, [], False, 0
        return frame.opcode, [frame.payload], frame.rsv1, current_message_size

    async def _handle_continuation_frame(
        self,
        frame,
        fragmented_opcode: int | None,
        fragments: list[bytes],
        fragmented_compressed: bool,
        current_message_size: int,
    ) -> tuple[int | None, list[bytes], bool, int]:
        if fragmented_opcode is None:
            raise ProtocolError('unexpected continuation frame')
        if frame.rsv1:
            raise ProtocolError('RSV1 is only valid on the first frame of a compressed message')
        current_message_size += len(frame.payload)
        self._ensure_message_size(current_message_size)
        fragments.append(frame.payload)
        if not frame.fin:
            return fragmented_opcode, fragments, fragmented_compressed, current_message_size
        payload = b''.join(fragments)
        if fragmented_compressed:
            runtime = self.state.get('permessage_deflate_runtime')
            if runtime is None:
                raise ProtocolError('RSV1 is not negotiated')
            payload = runtime.decompress_message(payload)
        await self._deliver_message(fragmented_opcode, payload)
        return None, [], False, 0

    async def _deliver_message(self, opcode: int, payload: bytes) -> None:
        if opcode == OP_TEXT:
            try:
                text = payload.decode('utf-8', 'strict')
            except UnicodeDecodeError as exc:
                raise _WebSocketCloseSignal(1007, 'invalid frame payload data') from exc
            await self.receive.put(websocket_receive_text(text))
            return
        await self.receive.put(websocket_receive_bytes(payload))
