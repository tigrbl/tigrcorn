from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from tigrcorn_protocols.http3.handler.webtransport_send import send_message


def _owner() -> SimpleNamespace:
    handler = SimpleNamespace(
        _send_webtransport_stream_data=AsyncMock(),
        _open_webtransport_server_stream=AsyncMock(return_value=7),
    )
    return SimpleNamespace(
        accepted=True,
        closed=False,
        session=object(),
        session_id="session-1",
        stream_id=4,
        server_stream_ids={},
        handler=handler,
        endpoint=object(),
        receive=SimpleNamespace(put=AsyncMock()),
        _trace_webtransport=lambda *args, **kwargs: None,
        _trace_session_fields=lambda: {},
    )


def test_multiple_records_keep_one_bidi_stream_open_until_explicit_terminal() -> None:
    async def exercise() -> None:
        owner = _owner()
        for payload in (b"one", b"two", b"three"):
            await send_message(
                owner,
                {
                    "type": "webtransport.stream.send",
                    "stream_id": "4",
                    "stream_direction": "bidi",
                    "data": payload,
                    "more": True,
                },
            )

        calls = owner.handler._send_webtransport_stream_data.await_args_list
        assert len(calls) == 3
        assert all(call.kwargs["end_stream"] is False for call in calls)

        await send_message(
            owner,
            {
                "type": "webtransport.stream.send",
                "stream_id": "4",
                "stream_direction": "bidi",
                "data": b"final",
                "more": False,
            },
        )
        assert (
            owner.handler._send_webtransport_stream_data.await_args.kwargs["end_stream"]
            is True
        )

    asyncio.run(exercise())


def test_missing_continuation_is_rejected_instead_of_inferred_as_fin() -> None:
    async def exercise() -> None:
        owner = _owner()
        with pytest.raises(RuntimeError, match="explicit boolean more"):
            await send_message(
                owner,
                {
                    "type": "webtransport.stream.send",
                    "stream_id": "4",
                    "stream_direction": "bidi",
                    "data": b"record",
                },
            )
        owner.handler._send_webtransport_stream_data.assert_not_awaited()

    asyncio.run(exercise())
