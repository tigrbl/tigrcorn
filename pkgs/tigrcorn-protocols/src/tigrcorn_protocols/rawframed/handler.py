from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from tigrcorn_asgi.events.custom import stream_receive
from tigrcorn_asgi.receive import QueueReceive
from tigrcorn_asgi.scopes.custom import build_custom_scope
from tigrcorn_config.model import ListenerConfig, ServerConfig
from tigrcorn_observability.logging import AccessLogger
from tigrcorn_protocols.custom.adapters import adapt_scope
from tigrcorn_protocols.rawframed.frames import encode_frame, try_decode_frame
from tigrcorn_protocols.rawframed.state import RawFramedState
from tigrcorn_core.types import ASGIApp


class _Writable(Protocol):
    def write(self, data: bytes) -> int: ...


@dataclass(slots=True)
class _RawAppSend:
    connection: _Writable
    outbound_frames: int = 0

    async def __call__(self, message: dict) -> None:
        typ = message.get('type')
        if typ != 'tigrcorn.stream.send':
            raise RuntimeError(f'unexpected raw framed send event: {typ!r}')
        payload = bytes(message.get('data', b''))
        self.connection.write(encode_frame(payload))
        self.outbound_frames += 1


@dataclass(slots=True)
class RawFramedApplicationHandler:
    app: ASGIApp
    config: ServerConfig
    listener: ListenerConfig
    access_logger: AccessLogger
    buffers: dict[int, bytearray] = field(default_factory=dict)
    states: dict[int, RawFramedState] = field(default_factory=dict)

    async def feed_bytes(self, connection: _Writable, data: bytes, *, path: str | None = None) -> int:
        key = id(connection)
        buffer = self.buffers.setdefault(key, bytearray())
        state = self.states.setdefault(key, RawFramedState())
        buffer.extend(data)
        handled = 0
        while True:
            frame = try_decode_frame(buffer)
            if frame is None:
                return handled
            state.frames_received += 1
            handled += 1
            await self._dispatch_frame(connection, frame.payload, state, path=path)

    async def _dispatch_frame(self, connection: _Writable, payload: bytes, state: RawFramedState, *, path: str | None = None) -> None:
        scope = adapt_scope(
            build_custom_scope(
                'tigrcorn.rawframed',
                scheme=self.listener.scheme or 'tigrcorn+raw',
                path=path or self.listener.path or '',
                headers=[],
                extensions={'tigrcorn.custom': {'transport': self.listener.kind}},
            )
        )
        receive = QueueReceive()
        await receive.put(stream_receive(payload, more_data=False))
        send = _RawAppSend(connection=connection)
        await self.app(scope, receive, send)
        state.frames_sent += send.outbound_frames
