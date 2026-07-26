from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from tigrcorn_protocols.http3.handler import HTTP3DatagramHandler


def test_http3_session_timer_enforces_local_quic_idle_timeout() -> None:
    async def scenario() -> None:
        handler = object.__new__(HTTP3DatagramHandler)
        handler._lock = asyncio.Lock()
        handler.config = SimpleNamespace(quic=SimpleNamespace(idle_timeout=10.0))
        session = SimpleNamespace(
            addr=("127.0.0.1", 4433),
            last_activity_at=time.monotonic() - 11,
            timer_handle=None,
        )
        handler.sessions = {session.addr: session}
        handler.trace_webtransport = Mock()
        handler._trace_session_fields = Mock(return_value={})
        handler._abort_session_tunnels = AsyncMock()
        handler._abort_session_websockets = AsyncMock()
        handler._abort_session_webtransports = AsyncMock()
        handler._close_session = Mock()
        endpoint = SimpleNamespace(
            transport=SimpleNamespace(is_closing=lambda: False)
        )

        await handler._on_session_timer(session, endpoint)

        handler._abort_session_webtransports.assert_awaited_once_with(session)
        handler._close_session.assert_called_once_with(session)

    asyncio.run(scenario())
