from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from tigrcorn.config import ListenerConfig, ServerConfig
from tigrcorn_protocols.http3.handler.core import HTTP3DatagramHandler, HTTP3Session
from tigrcorn_protocols.http3.handler.webtransport import _HTTP3WebTransportSession
from tigrcorn.utils.bytes import encode_quic_varint
from tigrcorn_protocols.webtransport.governance import (
    WebTransportBudgetPolicy,
    WebTransportGovernanceError,
    WebTransportGovernanceManager,
)


async def _app(scope, receive, send) -> None:
    return None


class _AccessLogger:
    def log_http(self, *args, **kwargs) -> None:
        return None


class _Streams:
    def __init__(self) -> None:
        self.next_server_unidirectional_id = 3

    def next_stream_id(
        self, *, client: bool = False, unidirectional: bool = False
    ) -> int:
        assert client is False
        assert unidirectional is True
        stream_id = self.next_server_unidirectional_id
        self.next_server_unidirectional_id += 4
        return stream_id


class _Quic:
    local_cid = b"local-cid"
    remote_cid = b"remote-cid"
    state = "active"
    address_validated = True

    def __init__(self) -> None:
        self.streams = _Streams()
        self.sent_streams: list[tuple[int, bytes, bool]] = []
        self.pending_control: list[bytes] = []

    def send_stream_data_packets(self, stream_id: int, data: bytes, *, fin: bool) -> list[bytes]:
        packet = self.send_stream_data(stream_id, data, fin=fin)
        if fin and stream_id % 4 == 0:
            self.pending_control.append(b"max-streams-credit")
        return [packet]

    def take_handshake_datagrams(self) -> list[bytes]:
        pending = list(self.pending_control)
        self.pending_control.clear()
        return pending
    def send_datagram_frame(self, payload: bytes) -> bytes:
        return b"datagram:" + payload

    def send_stream_data(self, stream_id: int, data: bytes, *, fin: bool) -> bytes:
        self.sent_streams.append((stream_id, data, fin))
        return b"stream-packet"


def _policy() -> WebTransportBudgetPolicy:
    return WebTransportBudgetPolicy(
        max_streams=1,
        max_datagram_size=4,
        max_datagrams_per_session=2,
        max_memory_bytes=16,
        max_bandwidth_bytes=32,
        max_peers=1,
        datagram_abuse_threshold=2,
    )


def _runtime() -> tuple[HTTP3DatagramHandler, HTTP3Session, _HTTP3WebTransportSession]:
    manager = WebTransportGovernanceManager(_policy())
    handler = HTTP3DatagramHandler(
        app=_app,
        config=ServerConfig(
            listeners=[
                ListenerConfig(
                    kind="udp",
                    host="127.0.0.1",
                    port=0,
                    protocols=["quic", "http3", "webtransport"],
                    quic_secret=b"wt-secret",
                )
            ]
        ),
        listener=ListenerConfig(kind="udp", host="127.0.0.1", port=0, protocols=["quic", "http3", "webtransport"]),
        access_logger=_AccessLogger(),
        webtransport_governance=manager,
    )
    handler._queue_session_outbound_locked = lambda *args, **kwargs: None
    session = HTTP3Session(addr=("203.0.113.10", 4433), quic=_Quic())
    session.runtime_id = "h3s-test"
    handler.sessions[session.addr] = session
    webtransport = _HTTP3WebTransportSession(
        handler=handler,
        session=session,
        stream_id=0,
        request=SimpleNamespace(
            path="/wt",
            raw_path=b"/wt",
            query_string=b"",
            headers=[],
        ),
        client=session.addr,
        server=("127.0.0.1", 4433),
        scheme="https",
        endpoint=SimpleNamespace(local_addr=("127.0.0.1", 4433), send=lambda *args, **kwargs: None),
    )
    session.webtransport_sessions[0] = webtransport
    session.webtransport_streams.add(0)
    session.webtransport_stream_owners[0] = 0
    return handler, session, webtransport


def test_webtransport_session_open_registers_budget_state() -> None:
    handler, session, webtransport = _runtime()

    registered = handler._webtransport_register_session(session, webtransport)
    snapshot = handler._webtransport_budget_snapshot()

    assert registered["session_id"] == webtransport.session_id
    assert registered["peer_id"] == "peer:addr:203.0.113.10:4433"
    assert snapshot["active_sessions"] == (webtransport.session_id,)
    assert snapshot["sessions"][webtransport.session_id]["address"] == "203.0.113.10:4433"


def test_webtransport_stream_open_enforces_runtime_budget() -> None:
    handler, session, webtransport = _runtime()
    handler._webtransport_register_session(session, webtransport)

    handler._webtransport_register_stream(webtransport, 0)
    with pytest.raises(WebTransportGovernanceError, match="stream budget"):
        handler._webtransport_register_stream(webtransport, 4)

    snapshot = handler._webtransport_budget_snapshot()
    assert snapshot["sessions"][webtransport.session_id]["streams"] == ("0",)

    handler._webtransport_release_stream(webtransport, 0)
    handler._webtransport_register_stream(webtransport, 4)
    snapshot = handler._webtransport_budget_snapshot()
    assert snapshot["sessions"][webtransport.session_id]["streams"] == ("4",)


def test_webtransport_datagram_runtime_path_closes_on_abuse() -> None:
    handler, session, webtransport = _runtime()
    handler._webtransport_register_session(session, webtransport)

    async def run() -> None:
        payload = handler._encode_webtransport_datagram_payload(0, b"toolong")
        await handler._dispatch_webtransport_datagram_locked(session, payload)
        await handler._dispatch_webtransport_datagram_locked(session, payload)

    asyncio.run(run())
    snapshot = handler._webtransport_budget_snapshot()

    assert webtransport.closed is True
    assert snapshot["sessions"][webtransport.session_id]["closed"] is True
    assert snapshot["sessions"][webtransport.session_id]["close_reason"] == "datagram size budget exceeded"
    assert any(entry["event"] == "webtransport.datagram.budget.reject" for entry in handler.webtransport_trace)


def test_webtransport_rebinding_preserves_session_budget() -> None:
    handler, session, webtransport = _runtime()
    handler._webtransport_register_session(session, webtransport)
    handler._webtransport_register_datagram(webtransport, "d1", b"one")

    session.addr = ("203.0.113.10", 53000)
    handler._webtransport_register_rebinding(session)
    snapshot = handler._webtransport_budget_snapshot()
    state = snapshot["sessions"][webtransport.session_id]

    assert state["address"] == "203.0.113.10:53000"
    assert state["datagrams"] == 1
    assert state["closed"] is False


def test_webtransport_shutdown_releases_budgeted_resources() -> None:
    handler, session, webtransport = _runtime()
    handler._webtransport_register_session(session, webtransport)
    handler._webtransport_register_stream(webtransport, 0)

    asyncio.run(handler._abort_session_webtransports(session))
    snapshot = handler._webtransport_budget_snapshot()

    assert snapshot["active_sessions"] == ()
    assert snapshot["released_sessions"] == (webtransport.session_id,)
    assert snapshot["sessions"][webtransport.session_id]["streams"] == ()
    assert snapshot["sessions"][webtransport.session_id]["closed"] is True


def test_server_unidirectional_send_allocates_server_owned_quic_stream() -> None:
    handler, session, webtransport = _runtime()
    handler._webtransport_register_session(session, webtransport)
    handler._flush_qpack_streams = lambda _session: []

    async def run() -> None:
        await webtransport._send(
            {"type": "webtransport.accept", "session_id": webtransport.session_id}
        )
        await webtransport._send(
            {
                "type": "webtransport.stream.send",
                "session_id": webtransport.session_id,
                "stream_id": "room-event-1",
                "stream_direction": "server_to_client",
                "data": b"presence-event",
                "more": False,
            }
        )

    asyncio.run(run())
    stream_id, wire_data, fin = session.quic.sent_streams[-1]
    assert stream_id % 4 == 3
    assert wire_data == (
        encode_quic_varint(handler._WEBTRANSPORT_UNIDI_STREAM_SIGNAL)
        + encode_quic_varint(webtransport.stream_id)
        + b"presence-event"
    )
    assert fin is True
    assert webtransport.server_stream_ids == {}
    snapshot = handler._webtransport_budget_snapshot()
    assert snapshot["sessions"][webtransport.session_id]["streams"] == ()

def test_finished_client_bidi_response_immediately_emits_max_streams_credit() -> None:
    handler, session, webtransport = _runtime()
    handler._webtransport_register_session(session, webtransport)
    handler._flush_qpack_streams = lambda _session: []
    session.webtransport_streams.add(4)
    session.webtransport_stream_owners[4] = 0
    captured: list[bytes] = []
    handler._queue_session_outbound_locked = (
        lambda _session, outbound, _endpoint, **_kwargs: captured.extend(outbound)
    )

    asyncio.run(
        handler._send_webtransport_stream_data(
            session,
            4,
            b"rpc-response",
            end_stream=True,
            endpoint=webtransport.endpoint,
            priority=True,
        )
    )

    assert captured == [b"stream-packet", b"max-streams-credit"]