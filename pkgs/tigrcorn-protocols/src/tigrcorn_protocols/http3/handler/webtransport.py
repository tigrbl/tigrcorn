from __future__ import annotations

import asyncio
from contextlib import suppress
from itertools import count
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tigrcorn_protocols.http1.parser import ParsedRequest
    from tigrcorn_transports.udp.endpoint import UDPEndpoint

    from .core import HTTP3DatagramHandler, HTTP3Session


logger = logging.getLogger("tigrcorn")
WEBTRANSPORT_ASGI_CHUNK_SIZE = 16 * 1024


class _WebTransportReceive:
    """Lane-aware ASGI receive queue with FIFO ordering inside each priority."""

    def __init__(self, max_size: int | None = None) -> None:
        self._sequence = count()
        self._queue: asyncio.PriorityQueue[tuple[int, int, dict]] = (
            asyncio.PriorityQueue(maxsize=0 if not max_size else max_size)
        )

    @staticmethod
    def _priority(message: dict) -> int:
        event_type = str(message.get("type", ""))
        if event_type in {"webtransport.connect", "webtransport.disconnect"}:
            return 0
        if (
            event_type == "webtransport.stream.receive"
            and message.get("stream_direction") == "bidi"
        ):
            return 1
        if event_type == "webtransport.datagram.receive":
            return 2
        return 3

    async def put(self, message: dict) -> None:
        await self._queue.put((self._priority(message), next(self._sequence), message))

    async def __call__(self) -> dict:
        _priority, _sequence, message = await self._queue.get()
        return message


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
        h3_session_id = getattr(session, "runtime_id", "") or session.quic.local_cid.hex() or "session"
        self.session_id = f"h3-{h3_session_id}-{stream_id}"
        # A persistent stream can yield many packet-sized ASGI events. Stream
        # concurrency is therefore not a valid event-queue bound; retain a
        # bounded queue while allowing each admitted stream a useful window.
        self.receive = _WebTransportReceive(
            max_size=max(
                256, int(handler.config.webtransport.max_streams or 1) * 64
            )
        )
        self.task: asyncio.Task[None] | None = None
        self.accepted = False
        self.closed = False
        self.connect_stream_ended = False
        self.server_stream_ids: dict[str, int] = {}
        self.client_stream_buffers: dict[str, bytearray] = {}

    def _trace_session_fields(self) -> dict[str, object]:
        trace_fields = getattr(self.handler, "_trace_session_fields", None)
        if trace_fields is None:
            return {}
        return trace_fields(self.session)

    def _trace_webtransport(self, event: str, **fields: object) -> None:
        trace = getattr(self.handler, "trace_webtransport", None)
        if trace is not None:
            trace(event, **fields)

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
                    "h3_session_id": getattr(self.session, "runtime_id", ""),
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
        self._trace_webtransport(
            "webtransport.app.start",
            **self._trace_session_fields(),
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
        except Exception:
            logger.exception("WebTransport application failed")
            raise
        finally:
            self._trace_webtransport(
                "webtransport.app.complete",
                **self._trace_session_fields(),
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
                        priority=True,
                    )
            self.handler._on_webtransport_stream_closed(self.session, self.stream_id)

    async def _send(self, message: dict) -> None:
        typ = message.get("type")
        self._trace_webtransport(
            "webtransport.asgi.send",
            **self._trace_session_fields(),
            stream_id=message.get("stream_id", self.stream_id),
            session_id=self.session_id,
            owner_stream_id=self.stream_id,
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
            logical_stream_id = str(message.get("stream_id", self.stream_id))
            if stream_direction == "server_to_client":
                target_stream_id = self.server_stream_ids.get(logical_stream_id)
                if target_stream_id is None:
                    target_stream_id = await self.handler._open_webtransport_server_stream(
                        self.session,
                        self.stream_id,
                        endpoint=self.endpoint,
                    )
                    self.server_stream_ids[logical_stream_id] = target_stream_id
            else:
                target_stream_id = int(logical_stream_id)
            await self.handler._send_webtransport_stream_data(
                self.session,
                target_stream_id,
                bytes(message.get("data", b"")),
                end_stream=not bool(message.get("more", False)),
                endpoint=self.endpoint,
                priority=(
                    stream_direction == "bidi"
                    or logical_stream_id.startswith("event-")
                    or bool(message.get("priority", False))
                ),
            )
            if stream_direction == "server_to_client" and not bool(
                message.get("more", False)
            ):
                self.server_stream_ids.pop(logical_stream_id, None)
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
            if self.closed:
                return
            self.closed = True
            await self.handler._send_webtransport_stream_data(
                self.session,
                self.stream_id,
                b"",
                end_stream=True,
                endpoint=self.endpoint,
                priority=True,
            )
            return
        raise RuntimeError(f"unexpected webtransport send message: {typ!r}")

    async def feed_stream_data(
        self,
        data: bytes,
        *,
        end_stream: bool = False,
        disconnect_on_end: bool = False,
        stream_id: int | None = None,
        stream_direction: str = "bidi",
        framing: str | None = None,
    ) -> None:
        if self.closed:
            return
        event_stream_id = str(self.stream_id if stream_id is None else stream_id)
        if stream_direction == "client_to_server":
            await self._feed_client_stream_data(
                event_stream_id,
                data,
                end_stream=end_stream,
                framing=framing,
            )
            return
        await self._put_stream_event(
            event_stream_id,
            data,
            end_stream=end_stream,
            stream_direction=stream_direction,
            framing=framing,
        )
        if end_stream and disconnect_on_end and not self.closed:
            self.closed = True
            self._trace_webtransport(
                "webtransport.asgi.receive",
                **self._trace_session_fields(),
                stream_id=self.stream_id,
                session_id=self.session_id,
                type="webtransport.disconnect",
            )
            await self.receive.put({"type": "webtransport.disconnect", "session_id": self.session_id, "code": 0, "reason": ""})

    async def _feed_client_stream_data(
        self,
        stream_id: str,
        data: bytes,
        *,
        end_stream: bool,
        framing: str | None,
    ) -> None:
        buffer = self.client_stream_buffers.setdefault(stream_id, bytearray())
        buffer.extend(data)
        while len(buffer) >= WEBTRANSPORT_ASGI_CHUNK_SIZE:
            chunk = bytes(buffer[:WEBTRANSPORT_ASGI_CHUNK_SIZE])
            del buffer[:WEBTRANSPORT_ASGI_CHUNK_SIZE]
            final_chunk = end_stream and not buffer
            await self._put_stream_event(
                stream_id,
                chunk,
                end_stream=final_chunk,
                stream_direction="client_to_server",
                framing=framing,
            )
        if end_stream:
            if buffer or not data:
                await self._put_stream_event(
                    stream_id,
                    bytes(buffer),
                    end_stream=True,
                    stream_direction="client_to_server",
                    framing=framing,
                )
            self.client_stream_buffers.pop(stream_id, None)

    async def _put_stream_event(
        self,
        stream_id: str,
        data: bytes,
        *,
        end_stream: bool,
        stream_direction: str,
        framing: str | None,
    ) -> None:
        # QUIC may deliver FIN in a zero-length STREAM frame after the final
        # data frame. Surface that terminal event so applications can finish
        # buffering a message previously delivered with `more=True`.
        if data or end_stream:
            event = {
                "type": "webtransport.stream.receive",
                "session_id": self.session_id,
                "stream_id": stream_id,
                "stream_direction": stream_direction,
                "data": data,
                "more": not end_stream,
            }
            if framing is not None:
                event["framing"] = framing
            self._trace_webtransport(
                "webtransport.asgi.receive",
                **self._trace_session_fields(),
                stream_id=stream_id,
                session_id=self.session_id,
                owner_stream_id=self.stream_id,
                type="webtransport.stream.receive",
                stream_direction=stream_direction,
                bytes=len(data),
                fin=bool(end_stream),
            )
            await self.receive.put(event)

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
        self._trace_webtransport(
            "webtransport.asgi.receive",
            **self._trace_session_fields(),
            session_id=self.session_id,
            owner_stream_id=self.stream_id,
            type="webtransport.datagram.receive",
            datagram_id=datagram_id,
            bytes=len(data),
        )
        await self.receive.put(event)

    async def abort(self) -> None:
        if self.closed:
            return
        self._trace_webtransport(
            "webtransport.app.abort",
            **self._trace_session_fields(),
            stream_id=self.stream_id,
            session_id=self.session_id,
        )
        await self.receive.put(
            {
                "type": "webtransport.disconnect",
                "session_id": self.session_id,
                "code": 0,
                "reason": "transport-closed",
            }
        )
        self.client_stream_buffers.clear()
        if self.task is not None:
            try:
                await asyncio.wait_for(asyncio.shield(self.task), timeout=1.0)
            except TimeoutError:
                self.task.cancel()
                with suppress(asyncio.CancelledError):
                    await self.task
        self.closed = True
