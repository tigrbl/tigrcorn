from __future__ import annotations

import asyncio
from types import SimpleNamespace

from tigrcorn_protocols.http3.handler.webtransport import _HTTP3WebTransportSession


class _LocalCid(bytes):
    def hex(self) -> str:
        return "localcid"


def _transport(*, fail: bool = False):
    sent: list[dict] = []

    async def open_stream(*args, **kwargs) -> int:
        return 7

    async def send_stream(session, stream_id, data, **kwargs) -> None:
        if fail:
            raise OSError("transport write failed")
        sent.append({"stream_id": stream_id, "data": data, **kwargs})

    handler = SimpleNamespace(
        config=SimpleNamespace(webtransport=SimpleNamespace(max_streams=4)),
        _open_webtransport_server_stream=open_stream,
        _send_webtransport_stream_data=send_stream,
        _trace_session_fields=lambda session: {},
    )
    session = SimpleNamespace(
        runtime_id="session-1",
        quic=SimpleNamespace(local_cid=_LocalCid(b"localcid")),
    )
    return (
        _HTTP3WebTransportSession(
            handler=handler,
            session=session,
            stream_id=0,
            request=SimpleNamespace(),
            client=("127.0.0.1", 10001),
            server=("127.0.0.1", 443),
            scheme="https",
            endpoint=SimpleNamespace(),
        ),
        sent,
    )


def test_correlated_stream_send_reports_flushed_completion() -> None:
    async def exercise() -> None:
        transport, sent = _transport()
        await transport._send({"type": "webtransport.accept"})
        await transport._send(
            {
                "type": "webtransport.stream.send",
                "stream_id": "events-1",
                "stream_direction": "server_to_client",
                "data": b"event",
                "more": False,
                "emit_id": "emit-1",
            }
        )

        assert sent[0]["end_stream"] is True
        assert await transport.receive() == {
            "type": "transport.emit.complete",
            "emit_id": "emit-1",
            "level": "flushed_to_transport",
            "status": "ok",
            "session_id": transport.session_id,
            "stream_id": "events-1",
            "stream_direction": "server_to_client",
        }

    asyncio.run(exercise())


def test_correlated_stream_send_reports_failure_before_reraising() -> None:
    async def exercise() -> None:
        transport, _ = _transport(fail=True)
        await transport._send({"type": "webtransport.accept"})
        try:
            await transport._send(
                {
                    "type": "webtransport.stream.send",
                    "stream_id": "events-1",
                    "stream_direction": "server_to_client",
                    "data": b"event",
                    "emit_id": "emit-2",
                }
            )
        except OSError:
            pass
        else:
            raise AssertionError("expected transport write failure")

        event = await transport.receive()
        assert event["type"] == "transport.emit.failed"
        assert event["emit_id"] == "emit-2"
        assert event["level"] == "failed_during_emit"
        assert event["status"] == "failed"
        assert event["retryable"] is True

    asyncio.run(exercise())