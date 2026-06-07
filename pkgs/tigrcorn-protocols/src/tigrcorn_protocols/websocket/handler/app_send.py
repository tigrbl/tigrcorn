from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from tigrcorn_config.model import ServerConfig
from tigrcorn_core.utils.headers import get_header
from tigrcorn_protocols.flow.keepalive import KeepAliveRuntime
from tigrcorn_protocols.http1.serializer import serialize_http11_response_head, serialize_http11_response_whole
from tigrcorn_protocols.websocket.codec import binary_frame, close_frame, text_frame
from tigrcorn_protocols.websocket.extensions import (
    PerMessageDeflateRuntime,
    default_permessage_deflate_agreement,
    negotiate_permessage_deflate,
)
from tigrcorn_protocols.websocket.frames import OP_TEXT, serialize_frame
from tigrcorn_protocols.websocket.handshake import build_handshake_response


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
            await self._send_accept(message)
            return
        if typ == 'websocket.send':
            await self._send_message(message)
            return
        if typ == 'websocket.close':
            await self._send_close(message)
            return
        if typ == 'websocket.http.response.start':
            if self.state['accepted']:
                raise RuntimeError('cannot send websocket.http.response.start after accept')
            self.state['http_denial_status'] = int(message['status'])
            self.state['http_denial_headers'] = list(message.get('headers', []))
            self.state['http_denied'] = True
            return
        if typ == 'websocket.http.response.body':
            await self._send_denial_body(message)
            return
        raise RuntimeError(f'unexpected websocket send message: {typ!r}')

    async def _send_accept(self, message: dict) -> None:
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

    async def _send_message(self, message: dict) -> None:
        if not self.state['accepted']:
            raise RuntimeError('websocket.send before websocket.accept')
        if self.state['closed']:
            return
        text = message.get('text')
        data = message.get('bytes')
        if text is not None and data is not None:
            raise RuntimeError('websocket.send cannot contain both text and bytes')
        runtime = self.state.get('permessage_deflate_runtime')
        if text is not None:
            if runtime is not None:
                await self._write(serialize_frame(OP_TEXT, runtime.compress_message(text.encode('utf-8')), rsv1=True))
            else:
                await self._write(text_frame(text))
        else:
            raw = data or b''
            await self._write(binary_frame(runtime.compress_message(raw), rsv1=True) if runtime is not None else binary_frame(raw))
        self._record_activity()

    async def _send_close(self, message: dict) -> None:
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

    async def _send_denial_body(self, message: dict) -> None:
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
