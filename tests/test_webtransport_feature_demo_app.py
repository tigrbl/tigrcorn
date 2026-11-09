from __future__ import annotations

import asyncio
import os
from unittest.mock import patch

from examples.webtransport_mtls_demo.server import app as demo_app

def test_webtransport_demo_app_accepts_local_session_and_sends_initial_datagram() -> None:
    sent: list[dict[str, object]] = []

    async def receive() -> dict[str, object]:
        return {"type": "webtransport.close", "session_id": "s1"}

    async def send(event: dict[str, object]) -> None:
        sent.append(event)

    asyncio.run(
        demo_app(
            {
                "type": "webtransport",
                "path": "/wt",
                "extensions": {"tigrcorn.security": {"tls": True, "mtls": False}, "tigrcorn.unit": {"session_id": "s1"}},
            },
            receive,
            send,
        )
    )

    assert sent[0] == {"type": "webtransport.accept", "session_id": "s1"}
    assert sent[1]["type"] == "webtransport.datagram.send"


def test_webtransport_demo_app_echoes_stream_payloads() -> None:
    sent: list[dict[str, object]] = []
    events = iter(
        [
            {"type": "webtransport.stream.receive", "session_id": "s1", "stream_id": "st1", "stream_direction": "bidi", "data": b"payload"},
            {"type": "webtransport.close", "session_id": "s1"},
        ]
    )

    async def receive() -> dict[str, object]:
        return next(events)

    async def send(event: dict[str, object]) -> None:
        sent.append(event)

    asyncio.run(
        demo_app(
            {
                "type": "webtransport",
                "path": "/wt",
                "extensions": {"tigrcorn.security": {"tls": True, "mtls": False}, "tigrcorn.unit": {"session_id": "s1"}},
            },
            receive,
            send,
        )
    )

    assert {"type": "webtransport.stream.send", "session_id": "s1", "stream_id": "st1", "stream_direction": "bidi", "data": b"echo:payload", "more": False} in sent


def test_webtransport_demo_app_echoes_datagram_payloads() -> None:
    sent: list[dict[str, object]] = []
    events = iter(
        [
            {"type": "webtransport.datagram.receive", "session_id": "s1", "datagram_id": "d1", "data": b"payload"},
            {"type": "webtransport.close", "session_id": "s1"},
        ]
    )

    async def receive() -> dict[str, object]:
        return next(events)

    async def send(event: dict[str, object]) -> None:
        sent.append(event)

    asyncio.run(
        demo_app(
            {
                "type": "webtransport",
                "path": "/wt",
                "extensions": {"tigrcorn.security": {"tls": True, "mtls": False}, "tigrcorn.unit": {"session_id": "s1"}},
            },
            receive,
            send,
        )
    )

    assert {"type": "webtransport.datagram.send", "session_id": "s1", "datagram_id": "d1", "data": b"ack:payload"} in sent


def test_webtransport_demo_app_rejects_non_mtls_when_strict() -> None:
    sent: list[dict[str, object]] = []

    async def receive() -> dict[str, object]:
        raise AssertionError("strict mTLS rejection must not await receive")

    async def send(event: dict[str, object]) -> None:
        sent.append(event)

    with patch.dict(os.environ, {"TIGRCORN_DEMO_REQUIRE_MTLS": "true"}, clear=False):
        asyncio.run(
            demo_app(
                {
                    "type": "webtransport",
                    "path": "/wt",
                    "extensions": {"tigrcorn.security": {"tls": True, "mtls": False}, "tigrcorn.unit": {"session_id": "s1"}},
                },
                receive,
                send,
            )
        )

    assert sent == [{"type": "webtransport.close", "session_id": "s1", "code": 403, "reason": "mTLS required"}]


def test_webtransport_demo_app_accepts_mtls_when_strict() -> None:
    sent: list[dict[str, object]] = []

    async def receive() -> dict[str, object]:
        return {"type": "webtransport.close", "session_id": "s1"}

    async def send(event: dict[str, object]) -> None:
        sent.append(event)

    with patch.dict(os.environ, {"TIGRCORN_DEMO_REQUIRE_MTLS": "true"}, clear=False):
        asyncio.run(
            demo_app(
                {
                    "type": "webtransport",
                    "path": "/wt",
                    "extensions": {"tigrcorn.security": {"tls": True, "mtls": True}, "tigrcorn.unit": {"session_id": "s1"}},
                },
                receive,
                send,
            )
        )

    assert sent[0] == {"type": "webtransport.accept", "session_id": "s1"}
