from __future__ import annotations

import asyncio

from tigrcorn_protocols.http3.handler.webtransport import _WebTransportReceive


def test_webtransport_receive_prioritizes_lifecycle_and_control_lanes() -> None:
    async def scenario() -> None:
        receive = _WebTransportReceive()
        await receive.put(
            {
                "type": "webtransport.stream.receive",
                "stream_direction": "client_to_server",
                "stream_id": "media-1",
            }
        )
        await receive.put(
            {
                "type": "webtransport.stream.receive",
                "stream_direction": "bidi",
                "stream_id": "rpc-1",
            }
        )
        await receive.put({"type": "webtransport.disconnect"})

        assert (await receive())["type"] == "webtransport.disconnect"
        assert (await receive())["stream_id"] == "rpc-1"
        assert (await receive())["stream_id"] == "media-1"

    asyncio.run(scenario())


def test_webtransport_receive_preserves_fifo_within_a_lane() -> None:
    async def scenario() -> None:
        receive = _WebTransportReceive()
        for stream_id in ("media-1", "media-2", "media-3"):
            await receive.put(
                {
                    "type": "webtransport.stream.receive",
                    "stream_direction": "client_to_server",
                    "stream_id": stream_id,
                }
            )

        assert [(await receive())["stream_id"] for _ in range(3)] == [
            "media-1",
            "media-2",
            "media-3",
        ]

    asyncio.run(scenario())
