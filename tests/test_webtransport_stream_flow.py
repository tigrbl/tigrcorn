from __future__ import annotations

import asyncio
from types import SimpleNamespace

from tigrcorn_protocols.http3.handler.webtransport_stream_flow import (
    _STREAM_CHUNK_BYTES,
    send_nonpriority_stream_data,
)


def test_nonpriority_stream_send_waits_between_bounded_chunks() -> None:
    asyncio.run(_bounded_chunks_case())


async def _bounded_chunks_case() -> None:
    session = SimpleNamespace(
        addr=("127.0.0.1", 50000),
        lock=asyncio.Lock(),
        pending_outbound=[],
    )

    class _Handler:
        def __init__(self) -> None:
            self.sessions = {session.addr: session}
            self.sent: list[tuple[bytes, bool]] = []

        def _flush_pending_outbound(self, _session, _endpoint) -> None:
            return None

        async def _send_webtransport_stream_data(
            self,
            _session,
            _stream_id,
            data,
            *,
            end_stream,
            endpoint,
            already_locked,
            priority,
        ) -> None:
            del endpoint
            assert already_locked is True
            assert priority is False
            self.sent.append((data, end_stream))
            session.pending_outbound.append(object())

    handler = _Handler()
    payload = b"x" * (_STREAM_CHUNK_BYTES * 2 + 7)
    task = asyncio.create_task(
        send_nonpriority_stream_data(
            handler,
            session,
            3,
            payload,
            end_stream=True,
            endpoint=object(),
        )
    )

    await asyncio.sleep(0.01)
    assert handler.sent == [(payload[:_STREAM_CHUNK_BYTES], False)]

    for expected_count in (2, 3):
        session.pending_outbound.clear()
        for _ in range(20):
            if len(handler.sent) == expected_count:
                break
            await asyncio.sleep(0.001)
        assert len(handler.sent) == expected_count

    session.pending_outbound.clear()
    await asyncio.wait_for(task, timeout=0.2)

    assert [len(chunk) for chunk, _fin in handler.sent] == [
        _STREAM_CHUNK_BYTES,
        _STREAM_CHUNK_BYTES,
        7,
    ]
    assert [fin for _chunk, fin in handler.sent] == [False, False, True]
