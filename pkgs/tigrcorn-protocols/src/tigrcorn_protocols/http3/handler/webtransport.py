from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import TYPE_CHECKING

from tigrcorn_asgi.receive import QueueReceive

if TYPE_CHECKING:
    from tigrcorn_protocols.http1.parser import ParsedRequest
    from tigrcorn_transports.udp.endpoint import UDPEndpoint

    from .core import HTTP3DatagramHandler, HTTP3Session


class _HTTP3WebTransportSession:
    def __init__(
        self,
        *,
        handler: HTTP3DatagramHandler,
        session: HTTP3Session,
        stream_id: int,
        request: ParsedRequest,
        client: tuple[str, int] | None,
        server: tuple[str, int] | tuple[str, None] | None,
        scheme: str,
        endpoint: UDPEndpoint,
        work_lease: object | None = None,
    ) -> None:
        self.handler = handler
        self.session = session
        self.stream_id = stream_id
        self.request = request
        self.client = client
        self.server = server
        self.scheme = scheme
        self.endpoint = endpoint
        self.work_lease = work_lease
        self.session_id = f"h3-{stream_id}"
        self.receive = QueueReceive(max_size=handler.config.webtransport.max_streams)
        self.task: asyncio.Task[None] | None = None
        self.accepted = False
        self.closed = False
        self.connect_stream_ended = False

    async def start(self) -> None:
        scope = {
            "type": "webtransport",
            "asgi": {"version": "3.0", "spec_version": "2.5"},
            "http_version": "3",
            "scheme": self.scheme,
            "path": self.request.path,
            "raw_path": self.request.raw_path,
            "query_string": self.request.query_string,
            "headers": self.request.headers,
            "client": self.client,
            "server": self.server,
            "session_id": self.session_id,
            "ext": {
                "transport": {
                    "binding": "webtransport",
                    "alpn": "h3",
                    "secure": self.scheme in {"https", "wss"},
                    "quic": {"connection_id": self.session.quic.local_cid.hex()},
                },
                "webtransport": {
                    "supports_bidi_streams": True,
                    "supports_uni_streams": True,
                    "supports_datagrams": True,
                    "session_id": self.session_id,
                },
            },
            "extensions": {
                "h3": {"datagram": True, "stream_id": self.stream_id},
                "quic": {"connection_id": self.session.quic.local_cid.hex()},
                "tigrcorn.security": self.handler._webtransport_security_extension(self.session),
                "tigrcorn.transport": self.handler._webtransport_transport_extension(self.session),
                "tigrcorn.unit": {"session_id": self.session_id},
                "tigrcorn.webtransport": {"max_datagram_size": self.handler._webtransport_max_datagram_size()},
            },
        }
        self.handler.trace_webtransport(
            "webtransport.app.start",
            **self.handler._trace_session_fields(self.session),
            stream_id=self.stream_id,
            session_id=self.session_id,
            path=self.request.path,
        )
        await self.receive.put({"type": "webtransport.connect", "session_id": self.session_id})
        self.task = asyncio.create_task(
            self._start_webtransport_app(scope),
            name=f"tigrcorn-h3-webtransport-{self.stream_id}",
        )

    async def _start_webtransport_app(self, scope: dict) -> None:
        try:
            await self.handler.app(scope, self.receive, self._send)
        finally:
            self.handler.trace_webtransport(
                "webtransport.app.complete",
                **self.handler._trace_session_fields(self.session),
                stream_id=self.stream_id,
                session_id=self.session_id,
                closed=bool(self.closed),
            )
            if not self.closed:
                self.closed = True
                with suppress(Exception):
                    await self.handler._send_webtransport_stream_data(
                        self.session,
                        self.stream_id,
                        b"",
                        end_stream=True,
                        endpoint=self.endpoint,
                    )
            self.handler._on_webtransport_stream_closed(self.session, self.stream_id)

    async def _send(self, message: dict) -> None:
        typ = message.get("type")
        self.handler.trace_webtransport(
            "webtransport.asgi.send",
            **self.handler._trace_session_fields(self.session),
            stream_id=message.get("stream_id", self.stream_id),
            session_id=self.session_id,
            type=str(typ),
            bytes=len(bytes(message.get("data", b""))) if message.get("data") is not None else None,
        )
        if typ == "webtransport.accept":
            if self.accepted:
                raise RuntimeError("webtransport.accept sent more than once")
            self.accepted = True
            return
        if typ == "webtransport.stream.send":
            if not self.accepted:
                raise RuntimeError("webtransport.stream.send before webtransport.accept")
            stream_direction = str(message.get("stream_direction", "bidi"))
            if stream_direction not in {"bidi", "server_to_client"}:
                raise RuntimeError("webtransport.stream.send requires bidi or server_to_client stream_direction")
            target_stream_id = int(message.get("stream_id", self.stream_id))
            await self.handler._send_webtransport_stream_data(
                self.session,
                target_stream_id,
                bytes(message.get("data", b"")),
                end_stream=not bool(message.get("more", False)),
                endpoint=self.endpoint,
            )
            return
        if typ and str(typ).startswith("webtransport.message."):
            raise RuntimeError("webtransport message is not a native WebTransport lane")
        if typ == "webtransport.datagram.send":
            if not self.accepted:
                raise RuntimeError("webtransport.datagram.send before webtransport.accept")
            await self.handler._send_webtransport_datagram(
                self.session,
                self.stream_id,
                bytes(message.get("data", b"")),
                datagram_id=str(message.get("datagram_id", "datagram")),
                endpoint=self.endpoint,
            )
            return
        if typ in {"webtransport.close", "webtransport.disconnect"}:
            self.closed = True
            await self.handler._send_webtransport_stream_data(
                self.session,
                self.stream_id,
                b"",
                end_stream=True,
                endpoint=self.endpoint,
            )
            return
        raise RuntimeError(f"unexpected webtransport send message: {typ!r}")

    async def feed_stream_data(
        self,
        data: bytes,
        *,
        end_stream: bool = False,
        disconnect_on_end: bool = True,
        stream_id: int | None = None,
        stream_direction: str = "bidi",
        framing: str | None = None,
    ) -> None:
        if self.closed:
            return
        event_stream_id = str(self.stream_id if stream_id is None else stream_id)
        if data:
            event = {
                "type": "webtransport.stream.receive",
                "session_id": self.session_id,
                "stream_id": event_stream_id,
                "stream_direction": stream_direction,
                "data": data,
                "more": not end_stream,
            }
            if framing is not None:
                event["framing"] = framing
            self.handler.trace_webtransport(
                "webtransport.asgi.receive",
                **self.handler._trace_session_fields(self.session),
                stream_id=event_stream_id,
                session_id=self.session_id,
                type="webtransport.stream.receive",
                bytes=len(data),
                fin=bool(end_stream),
            )
            await self.receive.put(event)
        if end_stream and disconnect_on_end and not self.closed:
            self.closed = True
            self.handler.trace_webtransport(
                "webtransport.asgi.receive",
                **self.handler._trace_session_fields(self.session),
                stream_id=self.stream_id,
                session_id=self.session_id,
                type="webtransport.disconnect",
            )
            await self.receive.put({"type": "webtransport.disconnect", "session_id": self.session_id, "code": 0, "reason": ""})

    async def feed_connect_stream_data(self, data: bytes, *, end_stream: bool = False) -> None:
        if self.closed:
            return
        await self.feed_stream_data(data, end_stream=end_stream, disconnect_on_end=False, stream_direction="bidi")
        if end_stream:
            self.connect_stream_ended = True

    def note_connect_stream_stopped(self) -> None:
        self.connect_stream_ended = True

    async def feed_datagram(self, datagram_id: str, data: bytes, *, framing: str | None = None) -> None:
        if self.closed:
            return
        event = {
            "type": "webtransport.datagram.receive",
            "session_id": self.session_id,
            "datagram_id": datagram_id,
            "data": data,
        }
        if framing is not None:
            event["framing"] = framing
        self.handler.trace_webtransport(
            "webtransport.asgi.receive",
            **self.handler._trace_session_fields(self.session),
            session_id=self.session_id,
            type="webtransport.datagram.receive",
            datagram_id=datagram_id,
            bytes=len(data),
        )
        await self.receive.put(event)

    async def abort(self) -> None:
        self.closed = True
        self.handler.trace_webtransport(
            "webtransport.app.abort",
            **self.handler._trace_session_fields(self.session),
            stream_id=self.stream_id,
            session_id=self.session_id,
        )
        if self.task is not None:
            self.task.cancel()
            with suppress(asyncio.CancelledError):
                await self.task
