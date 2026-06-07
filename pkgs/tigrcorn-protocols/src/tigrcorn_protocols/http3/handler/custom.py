from __future__ import annotations

from .imports import *

class HTTP3CustomQuicMixin:
    async def _invoke_custom_quic_app(self, session: HTTP3Session, event: Any, endpoint: UDPEndpoint) -> list[bytes]:
        client = session.addr
        local = endpoint.local_addr
        server = (local[0], local[1]) if isinstance(local, tuple) and len(local) >= 2 else ('', None)
        scope = adapt_scope(
            build_custom_scope(
                'tigrcorn.quic',
                scheme=self.listener.scheme or 'quic',
                client=client,
                server=server,
                stream_id=event.stream_id,
                packet_number=event.packet_number,
                extensions={'tigrcorn.custom': {'transport': 'udp', 'protocol': 'quic'}},
            )
        )
        receive = _SingleEventReceive({'type': 'tigrcorn.stream.receive', 'data': event.data, 'more_data': not bool(event.fin)})
        send = _CustomQuicSend(session=session, stream_id=event.stream_id)
        await self.app(scope, receive, send)
        return send.flush()

class _SingleEventReceive:
    def __init__(self, event: dict) -> None:
        self.event = event
        self.sent = False

    async def __call__(self) -> dict:
        if not self.sent:
            self.sent = True
            return self.event
        return {'type': 'tigrcorn.stream.disconnect'}


class _CustomQuicSend:
    def __init__(self, *, session: HTTP3Session, stream_id: int | None) -> None:
        self.session = session
        self.stream_id = 0 if stream_id is None else stream_id
        self.messages: list[bytes] = []

    async def __call__(self, message: dict) -> None:
        typ = message.get('type')
        if typ != 'tigrcorn.stream.send':
            raise RuntimeError(f'unexpected custom quic send event: {typ!r}')
        data = bytes(message.get('data', b''))
        fin = not bool(message.get('more_data', False))
        self.messages.append(self.session.quic.send_stream_data(self.stream_id, data, fin=fin))

    def flush(self) -> list[bytes]:
        return list(self.messages)
