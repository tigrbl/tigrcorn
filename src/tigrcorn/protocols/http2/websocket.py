from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import Awaitable, Callable

from tigrcorn.flow.keepalive import KeepAlivePolicy, KeepAliveRuntime
from tigrcorn.observability.metrics import Metrics

from tigrcorn.asgi.events.websocket import websocket_connect, websocket_disconnect, websocket_receive_bytes, websocket_receive_text
from tigrcorn.asgi.receive import QueueReceive
from tigrcorn.asgi.scopes.websocket import build_websocket_scope
from tigrcorn.config.model import ServerConfig
from tigrcorn.errors import ProtocolError
from tigrcorn.protocols.http1.parser import ParsedRequest
from tigrcorn.protocols.websocket.codec import binary_frame, close_frame, pong_frame, text_frame
from tigrcorn.protocols.websocket.frames import OP_BINARY, OP_CLOSE, OP_CONT, OP_PING, OP_PONG, OP_TEXT, decode_close_payload, parse_frame_bytes, serialize_frame
from tigrcorn.protocols.websocket.extensions import PerMessageDeflateRuntime, default_permessage_deflate_agreement, negotiate_permessage_deflate, parse_permessage_deflate_offers
from tigrcorn.types import ASGIApp
from tigrcorn.utils.headers import get_header


class H2WebSocketSession:
    def __init__(
        self,
        *,
        app: ASGIApp,
        config: ServerConfig,
        request: ParsedRequest,
        client: tuple[str, int] | None,
        server: tuple[str, int] | tuple[str, None] | None,
        scheme: str,
        send_headers: Callable[[int, list[tuple[bytes, bytes]], bool], Awaitable[None]],
        send_data: Callable[[bytes, bool], Awaitable[None]],
        metrics: Metrics | None = None,
        on_close: Callable[[], None] | None = None,
    ) -> None:
        self.app = app
        self.config = config
        self.request = request
        self.client = client
        self.server = server
        self.scheme = 'wss' if scheme == 'https' else 'ws'
        self.send_headers = send_headers
        self.send_data = send_data
        self.metrics = metrics
        self.on_close = on_close
        self.receive = QueueReceive()
        self.task: asyncio.Task[None] | None = None
        self.accepted = False
        self.closed = False
        self.http_denied = False
        self.http_denial_status = 403
        self.http_denial_headers: list[tuple[bytes, bytes]] = []
        self.http_denial_started = False
        self.subprotocols = build_websocket_scope(request, client=client, server=server, scheme=self.scheme, root_path=self.config.proxy.root_path, proxy=self.config.proxy)['subprotocols']
        self.buffer = bytearray()
        self.peer_end_stream_pending = False
        self.fragmented_opcode: int | None = None
        self.fragments: list[bytes] = []
        self.current_message_size = 0
        self.fragmented_compressed = False
        self.permessage_deflate_offers = parse_permessage_deflate_offers(request.headers)
        self.permessage_deflate_runtime: PerMessageDeflateRuntime | None = None
        self.keepalive_policy = KeepAlivePolicy(
            idle_timeout=self.config.http.idle_timeout,
            ping_interval=self.config.websocket.ping_interval,
            ping_timeout=self.config.websocket.ping_timeout,
        )
        self.keepalive = KeepAliveRuntime(self.keepalive_policy) if self.keepalive_policy.enabled else None
        self.keepalive_task: asyncio.Task[None] | None = None
        version = get_header(request.headers, b'sec-websocket-version')
        if version != b'13':
            raise ProtocolError('unsupported websocket version')

    async def start(self) -> None:
        scope = build_websocket_scope(self.request, client=self.client, server=self.server, scheme=self.scheme, root_path=self.config.proxy.root_path, proxy=self.config.proxy)
        await self.receive.put(websocket_connect())
        self.task = asyncio.create_task(self._run_app(scope), name=f'tigrcorn-h2-ws-{self.request.path}')
        if self.keepalive is not None:
            self.keepalive_task = asyncio.create_task(self._keepalive_loop(), name=f'tigrcorn-h2-ws-keepalive-{self.request.path}')

    def _record_activity(self) -> None:
        if self.keepalive is not None:
            self.keepalive.record_activity()

    def _notify_closed(self) -> None:
        if self.on_close is not None:
            callback = self.on_close
            self.on_close = None
            callback()

    async def _keepalive_loop(self) -> None:
        while not self.closed:
            await asyncio.sleep(0.05)
            if self.keepalive is None or self.closed:
                return
            if self.keepalive.ping_timed_out():
                if self.metrics is not None:
                    self.metrics.websocket_ping_timeout()
                if not self.closed:
                    await self.send_data(close_frame(1011, 'ping timeout'), True)
                self.closed = True
                self._notify_closed()
                await self.receive.put(websocket_disconnect(1011, 'ping timeout'))
                return
            payload = self.keepalive.next_ping_payload()
            if payload is None:
                continue
            if self.metrics is not None:
                self.metrics.websocket_ping_sent()
            await self.send_data(serialize_frame(OP_PING, payload), False)

    async def _run_app(self, scope: dict) -> None:
        try:
            await self.app(scope, self.receive, self._send)
        except Exception:
            if self.accepted and not self.closed:
                with suppress(Exception):
                    await self.send_data(close_frame(1011, 'internal error'), True)
            raise
        finally:
            if self.http_denied and not self.closed:
                if not self.http_denial_started:
                    await self.send_headers(self.http_denial_status, self.http_denial_headers, True)
                    self.http_denial_started = True
                self.closed = True
            elif not self.accepted and not self.closed:
                await self.send_headers(403, [], True)
                self.closed = True
            elif self.accepted and not self.closed:
                await self.send_data(close_frame(1000, ''), True)
                self.closed = True
            self._notify_closed()
            if self.keepalive_task is not None:
                self.keepalive_task.cancel()
                with suppress(asyncio.CancelledError):
                    await self.keepalive_task

    async def _send(self, message: dict) -> None:
        typ = message['type']
        if typ == 'websocket.accept':
            if self.accepted or self.http_denied:
                raise RuntimeError('websocket.accept sent more than once')
            subprotocol = message.get('subprotocol')
            if subprotocol is not None and subprotocol not in self.subprotocols:
                raise RuntimeError('websocket.accept selected a subprotocol not offered by the client')
            headers = [(bytes(k).lower(), bytes(v)) for k, v in message.get('headers', [])]
            if self.config.websocket.compression != 'permessage-deflate':
                headers = [(k, v) for k, v in headers if k != b'sec-websocket-extensions']
            elif self.permessage_deflate_offers and get_header(headers, b'sec-websocket-extensions') is None:
                default_agreement = default_permessage_deflate_agreement(self.permessage_deflate_offers)
                if default_agreement is not None:
                    headers = headers + [(b'sec-websocket-extensions', default_agreement.as_header_value())]
            response_headers = [(k, v) for k, v in headers if k not in {b'sec-websocket-extensions', b'sec-websocket-protocol'}]
            agreement = negotiate_permessage_deflate(
                request_headers=self.request.headers,
                response_headers=headers,
            )
            if agreement is not None:
                self.permessage_deflate_runtime = PerMessageDeflateRuntime(agreement)
                response_headers.append((b'sec-websocket-extensions', agreement.as_header_value()))
            if subprotocol is not None:
                response_headers.append((b'sec-websocket-protocol', subprotocol.encode('ascii')))
            await self.send_headers(200, response_headers, False)
            self.accepted = True
            self._record_activity()
            if self.buffer or self.peer_end_stream_pending:
                pending_end_stream = self.peer_end_stream_pending
                self.peer_end_stream_pending = False
                await self.feed_data(b'', end_stream=pending_end_stream)
            return
        if typ == 'websocket.send':
            if not self.accepted:
                raise RuntimeError('websocket.send before websocket.accept')
            if self.closed:
                return
            text = message.get('text')
            data = message.get('bytes')
            if text is not None and data is not None:
                raise RuntimeError('websocket.send cannot contain both text and bytes')
            if text is not None:
                payload = text.encode('utf-8')
                if self.permessage_deflate_runtime is not None:
                    await self.send_data(serialize_frame(OP_TEXT, self.permessage_deflate_runtime.compress_message(payload), rsv1=True), False)
                else:
                    await self.send_data(text_frame(text), False)
                self._record_activity()
            else:
                raw = data or b''
                if self.permessage_deflate_runtime is not None:
                    await self.send_data(binary_frame(self.permessage_deflate_runtime.compress_message(raw), rsv1=True), False)
                else:
                    await self.send_data(binary_frame(raw), False)
            self._record_activity()
            return
        if typ == 'websocket.close':
            code = int(message.get('code', 1000))
            reason = message.get('reason', '')
            if not self.accepted:
                self.http_denied = True
                self.http_denial_status = 403
                self.http_denial_headers = []
                return
            if not self.closed:
                await self.send_data(close_frame(code, reason), True)
                self.closed = True
                self._notify_closed()
            return
        if typ == 'websocket.http.response.start':
            if self.accepted:
                raise RuntimeError('cannot deny websocket after accept')
            self.http_denied = True
            self.http_denial_status = int(message['status'])
            self.http_denial_headers = list(message.get('headers', []))
            return
        if typ == 'websocket.http.response.body':
            if not self.http_denied:
                raise RuntimeError('websocket.http.response.body before denial start')
            body = bytes(message.get('body', b''))
            more = bool(message.get('more_body', False))
            if not self.http_denial_started:
                headers = list(self.http_denial_headers)
                if not more:
                    headers.append((b'content-length', str(len(body)).encode('ascii')))
                end_stream = (not body) and (not more)
                await self.send_headers(self.http_denial_status, headers, end_stream)
                self.http_denial_started = True
                if end_stream:
                    self.closed = True
                    return
            if body or not more:
                await self.send_data(body, not more)
            if not more:
                self.closed = True
            return
        raise RuntimeError(f'unexpected websocket send message: {typ!r}')

    def _frame_length(self, data: bytes) -> int | None:
        if len(data) < 2:
            return None
        masked = bool(data[1] & 0x80)
        length = data[1] & 0x7F
        pos = 2
        if length == 126:
            if len(data) < pos + 2:
                return None
            length = int.from_bytes(data[pos:pos + 2], 'big')
            pos += 2
        elif length == 127:
            if len(data) < pos + 8:
                return None
            length = int.from_bytes(data[pos:pos + 8], 'big')
            pos += 8
        if masked:
            pos += 4
        if len(data) < pos + length:
            return None
        return pos + length

    def _inflate_if_needed(self, frame_payload: bytes, rsv1: bool) -> bytes:
        if not rsv1:
            return frame_payload
        if self.permessage_deflate_runtime is None:
            raise ProtocolError('RSV1 is not negotiated')
        return self.permessage_deflate_runtime.decompress_message(frame_payload)

    async def feed_data(self, data: bytes, *, end_stream: bool = False) -> None:
        if self.closed:
            return
        self.buffer.extend(data)
        if end_stream:
            self.peer_end_stream_pending = True
        if not self.accepted and not self.http_denied:
            return
        while self.buffer:
            frame_len = self._frame_length(self.buffer)
            if frame_len is None:
                break
            raw = bytes(self.buffer[:frame_len])
            del self.buffer[:frame_len]
            frame = parse_frame_bytes(
                raw,
                expect_masked=True,
                max_payload_size=self.config.websocket_max_message_size,
                allow_rsv1=self.permessage_deflate_runtime is not None,
            )
            self._record_activity()
            if frame.opcode == OP_PING:
                await self.send_data(pong_frame(frame.payload), False)
                continue
            if frame.opcode == OP_PONG:
                if self.keepalive is not None:
                    self.keepalive.acknowledge_pong(frame.payload)
                continue
            if frame.opcode == OP_CLOSE:
                code, reason = decode_close_payload(frame.payload)
                if not self.closed:
                    await self.send_data(close_frame(code, reason), True)
                self.closed = True
                self._notify_closed()
                await self.receive.put(websocket_disconnect(code, reason))
                break
            if frame.opcode in {OP_TEXT, OP_BINARY}:
                if self.fragmented_opcode is not None:
                    raise ProtocolError('new data frame before fragmented message completion')
                self.current_message_size = len(frame.payload)
                if self.current_message_size > self.config.websocket_max_message_size:
                    raise ProtocolError('message too big')
                if frame.fin:
                    payload = self._inflate_if_needed(frame.payload, frame.rsv1)
                    if frame.opcode == OP_TEXT:
                        await self.receive.put(websocket_receive_text(payload.decode('utf-8')))
                    else:
                        await self.receive.put(websocket_receive_bytes(payload))
                    self.current_message_size = 0
                else:
                    self.fragmented_opcode = frame.opcode
                    self.fragmented_compressed = frame.rsv1
                    self.fragments = [frame.payload]
                continue
            if frame.opcode == OP_CONT:
                if self.fragmented_opcode is None:
                    raise ProtocolError('unexpected continuation frame')
                if frame.rsv1:
                    raise ProtocolError('RSV1 is only valid on the first frame of a compressed message')
                self.current_message_size += len(frame.payload)
                if self.current_message_size > self.config.websocket_max_message_size:
                    raise ProtocolError('message too big')
                self.fragments.append(frame.payload)
                if frame.fin:
                    message = b''.join(self.fragments)
                    if self.fragmented_compressed:
                        message = self._inflate_if_needed(message, True)
                    opcode = self.fragmented_opcode
                    self.fragmented_opcode = None
                    self.fragmented_compressed = False
                    self.fragments = []
                    self.current_message_size = 0
                    if opcode == OP_TEXT:
                        await self.receive.put(websocket_receive_text(message.decode('utf-8')))
                    else:
                        await self.receive.put(websocket_receive_bytes(message))
                continue
            raise ProtocolError('unsupported websocket opcode')
        if self.peer_end_stream_pending and not self.closed:
            self.peer_end_stream_pending = False
            self.closed = True
            self._notify_closed()
            await self.receive.put(websocket_disconnect(1000, ''))

    async def abort(self) -> None:
        if not self.closed:
            self.closed = True
            self._notify_closed()
            await self.receive.put(websocket_disconnect(1006, ''))
        if self.task is not None:
            self.task.cancel()
            with suppress(asyncio.CancelledError):
                await self.task
