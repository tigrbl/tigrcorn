from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass

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
from tigrcorn.protocols.websocket.extensions import PerMessageDeflateRuntime, negotiate_permessage_deflate, parse_permessage_deflate_offers
from tigrcorn.protocols.websocket.handshake import build_handshake_response, validate_client_handshake
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
    allowed_subprotocols: list[str]

    async def __call__(self, message: dict) -> None:
        typ = message['type']
        if typ == 'websocket.accept':
            if self.state['accepted'] or self.state['http_denied']:
                raise RuntimeError('websocket.accept sent more than once')
            subprotocol = message.get('subprotocol')
            if subprotocol is not None and subprotocol not in self.allowed_subprotocols:
                raise RuntimeError('websocket.accept selected a subprotocol not offered by the client')
            headers = [(bytes(k).lower(), bytes(v)) for k, v in message.get('headers', [])]
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
            )
            self.writer.write(payload)
            await self.writer.drain()
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
                    self.writer.write(serialize_frame(OP_TEXT, runtime.compress_message(text.encode('utf-8')), rsv1=True))
                else:
                    self.writer.write(text_frame(text))
            else:
                raw = data or b''
                runtime = self.state.get('permessage_deflate_runtime')
                if runtime is not None:
                    self.writer.write(binary_frame(runtime.compress_message(raw), rsv1=True))
                else:
                    self.writer.write(binary_frame(raw))
            await self.writer.drain()
            return
        if typ == 'websocket.close':
            code = int(message.get('code', 1000))
            reason = message.get('reason', '')
            if not self.state['accepted']:
                self.writer.write(
                    serialize_http11_response_whole(
                        status=403,
                        headers=[],
                        body=b'',
                        keep_alive=False,
                        server_header=self.server_header,
                    )
                )
                await self.writer.drain()
                self.state['http_denied'] = True
                self.state['closed'] = True
                return
            if not self.state['closed']:
                self.writer.write(close_frame(code, reason))
                await self.writer.drain()
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
                    )
                    self.writer.write(head)
                    if body:
                        self.writer.write(f'{len(body):X}'.encode('ascii') + b'\r\n' + body + b'\r\n')
                else:
                    self.writer.write(
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
                    self.writer.write(f'{len(body):X}'.encode('ascii') + b'\r\n' + body + b'\r\n')
                if not more:
                    self.writer.write(b'0\r\n\r\n')
                    self.state['closed'] = True
            await self.writer.drain()
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
        self.receive = QueueReceive()
        self.accepted = asyncio.Event()
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
            )['subprotocols'],
        )

    async def handle(self) -> None:
        scope = build_websocket_scope(
            self.request,
            client=self.client,
            server=self.server,
            scheme=self.scheme,
            extensions=self.scope_extensions,
        )
        self.send.allowed_subprotocols = scope['subprotocols']
        await self.receive.put(websocket_connect())
        reader_task = asyncio.create_task(self._frame_reader(), name='tigrcorn-ws-reader')
        try:
            await self.app(scope, self.receive, self.send)
        except Exception:
            if self.state['accepted'] and not self.state['closed']:
                with suppress(Exception):
                    self.writer.write(close_frame(1011, 'internal error'))
                    await self.writer.drain()
            raise
        finally:
            if not self.state['accepted'] and not self.state['http_denied']:
                self.writer.write(
                    serialize_http11_response_whole(
                        status=403,
                        headers=[],
                        body=b'',
                        keep_alive=False,
                        server_header=self.config.server_header_value,
                    )
                )
                await self.writer.drain()
                self.state['closed'] = True
            elif self.state['http_denied'] and not self.state['http_denial_started']:
                self.writer.write(
                    serialize_http11_response_whole(
                        status=self.state['http_denial_status'],
                        headers=self.state['http_denial_headers'],
                        body=b'',
                        keep_alive=False,
                        server_header=self.config.server_header_value,
                    )
                )
                await self.writer.drain()
                self.state['closed'] = True
            elif self.state['accepted'] and not self.state['closed']:
                self.writer.write(close_frame(1000, ''))
                await self.writer.drain()
                self.state['closed'] = True
            reader_task.cancel()
            with suppress(Exception):
                await reader_task
            self.access_logger.log_ws(self.client, self.request.path, 'accepted' if self.state['accepted'] else 'denied')

    def _ensure_message_size(self, size: int) -> None:
        if size > self.config.websocket_max_message_size:
            raise _WebSocketCloseSignal(1009, 'message too big')

    async def _fail_connection(self, code: int, reason: str) -> None:
        if not self.state['closed']:
            self.writer.write(close_frame(code, reason))
            await self.writer.drain()
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
                if frame.opcode == OP_PING:
                    self.writer.write(pong_frame(frame.payload))
                    await self.writer.drain()
                    continue
                if frame.opcode == OP_PONG:
                    continue
                if frame.opcode == OP_CLOSE:
                    code, reason = decode_close_payload(frame.payload)
                    if not self.state['closed']:
                        self.writer.write(close_frame(code, reason))
                        await self.writer.drain()
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
