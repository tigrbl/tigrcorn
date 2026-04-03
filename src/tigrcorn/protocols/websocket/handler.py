from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass, field
from time import monotonic

from tigrcorn.asgi.events.websocket import (
    websocket_connect,
    websocket_disconnect,
    websocket_receive_bytes,
    websocket_receive_text,
)
from tigrcorn.asgi.receive import QueueReceive
from tigrcorn.asgi.scopes.websocket import build_websocket_scope
from tigrcorn.config.model import ServerConfig
from tigrcorn.errors import ProtocolError
from tigrcorn.observability.logging import AccessLogger
from tigrcorn.observability.metrics import Metrics
from tigrcorn.protocols.http1.serializer import serialize_http11_response_head, serialize_http11_response_whole
from tigrcorn.protocols.websocket.codec import binary_frame, close_frame, pong_frame, text_frame
from tigrcorn.protocols.websocket.frames import serialize_frame
from tigrcorn.protocols.websocket.frames import (
    OP_BINARY,
    OP_CLOSE,
    OP_CONT,
    OP_PING,
    OP_PONG,
    OP_TEXT,
    decode_close_payload,
    read_frame,
)
from tigrcorn.protocols.websocket.extensions import PerMessageDeflateRuntime, default_permessage_deflate_agreement, negotiate_permessage_deflate, parse_permessage_deflate_offers
from tigrcorn.protocols.websocket.handshake import build_handshake_response, validate_client_handshake
from tigrcorn.flow.keepalive import KeepAlivePolicy, KeepAliveRuntime
from tigrcorn.types import ASGIApp
from tigrcorn.utils.headers import get_header


class _WebSocketCloseSignal(Exception):
    def __init__(self, code: int, reason: str) -> None:
        super().__init__(reason)
        self.code = code
        self.reason = reason


@dataclass(slots=True)
class _WSAppSend:
    writer: asyncio.StreamWriter
    server_header: bytes | None
    state: dict
    accepted: asyncio.Event
    allowed_subprotocols: list[str] = field(default_factory=list)
    include_date_header: bool = True
    default_headers: list[tuple[bytes, bytes]] = field(default_factory=list)
    config: ServerConfig | None = None
    write_lock: asyncio.Lock | None = None
    keepalive: KeepAliveRuntime | None = None

    async def _write(self, data: bytes) -> None:
        if self.write_lock is None:
            self.writer.write(data)
            self._record_activity()
            return
        async with self.write_lock:
            self.writer.write(data)
            await self.writer.drain()

    def _record_activity(self) -> None:
        if self.keepalive is not None:
            self.keepalive.record_activity()

    async def __call__(self, message: dict) -> None:
        typ = message['type']
        if typ == 'websocket.accept':
            if self.state['accepted'] or self.state['http_denied']:
                raise RuntimeError('websocket.accept sent more than once')
            subprotocol = message.get('subprotocol')
            if subprotocol is not None and subprotocol not in self.allowed_subprotocols:
                raise RuntimeError('websocket.accept selected a subprotocol not offered by the client')
            headers = [(bytes(k).lower(), bytes(v)) for k, v in message.get('headers', [])]
            if get_header(headers, b'sec-websocket-extensions') is not None:
                raise RuntimeError('websocket.accept must not override extension negotiation headers directly')
            compression_mode = self.config.websocket.compression if self.config is not None else 'off'
            if compression_mode == 'permessage-deflate' and self.state.get('permessage_deflate_offers'):
                default_agreement = default_permessage_deflate_agreement(self.state.get('permessage_deflate_offers') or [])
                if default_agreement is not None:
                    headers = headers + [(b'sec-websocket-extensions', default_agreement.as_header_value())]
            negotiated_extensions: list[tuple[bytes, bytes]] = []
            agreement = negotiate_permessage_deflate(
                request_headers=self.state.get('request_headers', []),
                response_headers=headers,
            )
            if agreement is not None:
                negotiated_extensions.append((b'sec-websocket-extensions', agreement.as_header_value()))
                self.state['permessage_deflate_runtime'] = PerMessageDeflateRuntime(agreement)
            if get_header(headers, b'sec-websocket-protocol') is not None:
                raise RuntimeError('use websocket.accept subprotocol instead of sec-websocket-protocol response headers')
            payload = build_handshake_response(
                self.state['sec_websocket_key'],
                subprotocol=subprotocol,
                headers=[(k, v) for k, v in headers if k != b'sec-websocket-extensions'] + negotiated_extensions,
                server_header=self.server_header,
                include_date_header=self.include_date_header,
                default_headers=self.default_headers,
            )
            await self._write(payload)
            self._record_activity()
            self.state['accepted'] = True
            self.accepted.set()
            return
        if typ == 'websocket.send':
            if not self.state['accepted']:
                raise RuntimeError('websocket.send before websocket.accept')
            if self.state['closed']:
                return
            text = message.get('text')
            data = message.get('bytes')
            if text is not None and data is not None:
                raise RuntimeError('websocket.send cannot contain both text and bytes')
            if text is not None:
                runtime = self.state.get('permessage_deflate_runtime')
                if runtime is not None:
                    await self._write(serialize_frame(OP_TEXT, runtime.compress_message(text.encode('utf-8')), rsv1=True))
                else:
                    await self._write(text_frame(text))
            else:
                raw = data or b''
                runtime = self.state.get('permessage_deflate_runtime')
                if runtime is not None:
                    await self._write(binary_frame(runtime.compress_message(raw), rsv1=True))
                else:
                    await self._write(binary_frame(raw))
            self._record_activity()
            return
        if typ == 'websocket.close':
            code = int(message.get('code', 1000))
            reason = message.get('reason', '')
            if not self.state['accepted']:
                await self._write(
                    serialize_http11_response_whole(
                        status=403,
                        headers=[],
                        body=b'',
                        keep_alive=False,
                        server_header=self.server_header,
                        include_date_header=self.include_date_header,
                        default_headers=self.default_headers,
                    )
                )
                self.state['http_denied'] = True
                self.state['closed'] = True
                return
            if not self.state['closed']:
                await self._write(close_frame(code, reason))
            self.state['closed'] = True
            return
        if typ == 'websocket.http.response.start':
            if self.state['accepted']:
                raise RuntimeError('cannot send websocket.http.response.start after accept')
            self.state['http_denial_status'] = int(message['status'])
            self.state['http_denial_headers'] = list(message.get('headers', []))
            self.state['http_denied'] = True
            return
        if typ == 'websocket.http.response.body':
            if not self.state['http_denied']:
                raise RuntimeError('websocket.http.response.body before denial start')
            body = message.get('body', b'')
            more = bool(message.get('more_body', False))
            if not self.state['http_denial_started']:
                if more:
                    head = serialize_http11_response_head(
                        status=self.state['http_denial_status'],
                        headers=self.state['http_denial_headers'],
                        keep_alive=False,
                        server_header=self.server_header,
                        chunked=True,
                        include_date_header=self.include_date_header,
                        default_headers=self.default_headers,
                    )
                    await self._write(head + (f'{len(body):X}'.encode('ascii') + b'\r\n' + body + b'\r\n' if body else b''))
                else:
                    await self._write(
                        serialize_http11_response_whole(
                            status=self.state['http_denial_status'],
                            headers=self.state['http_denial_headers'],
                            body=body,
                            keep_alive=False,
                            server_header=self.server_header,
                        )
                    )
                    self.state['closed'] = True
                self.state['http_denial_started'] = True
            else:
                if body:
                    await self._write(f'{len(body):X}'.encode('ascii') + b'\r\n' + body + b'\r\n')
                if not more:
                    await self._write(b'0\r\n\r\n')
                    self.state['closed'] = True
            self._record_activity()
            return
        raise RuntimeError(f'unexpected websocket send message: {typ!r}')


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
            allowed_subprotocols=build_websocket_scope(
                self.request,
                client=self.client,
                server=self.server,
                scheme=self.scheme,
                extensions=self.scope_extensions,
                root_path=self.config.proxy.root_path,
                proxy=self.config.proxy,
            )['subprotocols'],
            include_date_header=config.include_date_header,
            default_headers=list(config.default_response_headers),
            config=config,
            write_lock=self.write_lock,
            keepalive=self.keepalive,
        )

    async def handle(self) -> None:
        scope = build_websocket_scope(
            self.request,
            client=self.client,
            server=self.server,
            scheme=self.scheme,
            extensions=self.scope_extensions,
            root_path=self.config.proxy.root_path,
            proxy=self.config.proxy,
        )
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
                with suppress(Exception):
                    await self.keepalive_task
            reader_task.cancel()
            with suppress(Exception):
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
                if frame.opcode == OP_PING:
                    await self._write(pong_frame(frame.payload))
                    continue
                if frame.opcode == OP_PONG:
                    if self.keepalive is not None:
                        self.keepalive.acknowledge_pong(frame.payload)
                    continue
                if frame.opcode == OP_CLOSE:
                    code, reason = decode_close_payload(frame.payload)
                    if not self.state['closed']:
                        await self._write(close_frame(code, reason))
                    self.state['closed'] = True
                    await self.receive.put(websocket_disconnect(code, reason))
                    return

                opcode = frame.opcode
                if opcode in {OP_TEXT, OP_BINARY}:
                    if fragmented_opcode is not None:
                        raise ProtocolError('new data frame before fragmented message completion')
                    current_message_size = len(frame.payload)
                    self._ensure_message_size(current_message_size)
                    fragmented_opcode = opcode if not frame.fin else None
                    fragmented_compressed = frame.rsv1
                    if frame.fin:
                        runtime = self.state.get('permessage_deflate_runtime')
                        payload = runtime.decompress_message(frame.payload) if frame.rsv1 and runtime is not None else frame.payload
                        await self._deliver_message(opcode, payload)
                        current_message_size = 0
                    else:
                        fragments = [frame.payload]
                    continue
                if opcode == OP_CONT:
                    if fragmented_opcode is None:
                        raise ProtocolError('unexpected continuation frame')
                    if frame.rsv1:
                        raise ProtocolError('RSV1 is only valid on the first frame of a compressed message')
                    current_message_size += len(frame.payload)
                    self._ensure_message_size(current_message_size)
                    fragments.append(frame.payload)
                    if frame.fin:
                        payload = b''.join(fragments)
                        if fragmented_compressed:
                            runtime = self.state.get('permessage_deflate_runtime')
                            if runtime is None:
                                raise ProtocolError('RSV1 is not negotiated')
                            payload = runtime.decompress_message(payload)
                        opcode = fragmented_opcode
                        fragmented_opcode = None
                        fragments = []
                        fragmented_compressed = False
                        current_message_size = 0
                        await self._deliver_message(opcode, payload)
                    continue
                raise ProtocolError('unsupported websocket opcode')
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

    async def _deliver_message(self, opcode: int, payload: bytes) -> None:
        if opcode == OP_TEXT:
            try:
                text = payload.decode('utf-8', 'strict')
            except UnicodeDecodeError as exc:
                raise _WebSocketCloseSignal(1007, 'invalid frame payload data') from exc
            await self.receive.put(websocket_receive_text(text))
            return
        await self.receive.put(websocket_receive_bytes(payload))
