from __future__ import annotations

import asyncio

from tigrcorn.availability import DOS_WARNING_EVENT, dos_warning
from tigrcorn.protocols.http1.parser import read_http11_request_head
from tigrcorn.protocols.http3.codec import H3_EXCESSIVE_LOAD, HTTP3StreamError
from tigrcorn.protocols.http3.streams import HTTP3ConnectionCore
from tigrcorn.protocols.websocket.frames import OP_BINARY, parse_frame_bytes, serialize_frame
from tigrcorn.scheduler.cancellation import cancel_many_bounded
from tigrcorn.scheduler.tasks import TaskSet
from tigrcorn.errors import ProtocolError
import pytest


class _LimitedHeadReader:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    async def readuntil_limited(
        self,
        separator: bytes,
        *,
        limit: int,
        read_chunk_size: int | None = None,
    ) -> bytes:
        if len(self.payload) > limit:
            raise asyncio.LimitOverrunError(
                "request head exceeds configured HTTP/1.1 request-head limit",
                consumed=len(self.payload),
            )
        return self.payload


def test_http3_request_parse_buffer_exhaustion_fails_closed() -> None:
    core = HTTP3ConnectionCore(role="server", max_request_parse_buffer_size=8)

    with pytest.raises(HTTP3StreamError) as exc_info:
        core.receive_stream_data(0, b"\x01" * 9, fin=False)

    assert exc_info.value.error_code == H3_EXCESSIVE_LOAD
    request = core.get_request(0)
    assert request.state.abandoned is True
    assert request.state.parse_buffer == bytearray()


async def _exercise_http11_request_head_limit_fails_closed() -> None:
    payload = b"GET / HTTP/1.1\r\nHost: example.test\r\nX-Fill: " + (b"a" * 64) + b"\r\n\r\n"
    reader = _LimitedHeadReader(payload)

    with pytest.raises(ProtocolError, match="request head exceeds configured HTTP/1.1 request-head limit"):
        await read_http11_request_head(
            reader,
            max_header_size=32,
            max_incomplete_event_size=32,
            buffer_size=8,
        )


def test_http11_request_head_limit_fails_closed() -> None:
    asyncio.run(_exercise_http11_request_head_limit_fails_closed())


async def _exercise_websocket_upgrade_request_head_limit_fails_closed() -> None:
    payload = (
        b"GET /ws HTTP/1.1\r\n"
        b"Host: example.test\r\n"
        b"Connection: Upgrade\r\n"
        b"Upgrade: websocket\r\n"
        b"Sec-WebSocket-Version: 13\r\n"
        b"Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
        b"X-Fill: "
        + (b"a" * 64)
        + b"\r\n\r\n"
    )
    reader = _LimitedHeadReader(payload)

    with pytest.raises(ProtocolError, match="request head exceeds configured HTTP/1.1 request-head limit"):
        await read_http11_request_head(
            reader,
            max_header_size=96,
            max_incomplete_event_size=96,
            buffer_size=8,
        )


def test_websocket_upgrade_request_head_limit_fails_closed() -> None:
    asyncio.run(_exercise_websocket_upgrade_request_head_limit_fails_closed())


def test_websocket_oversized_frame_fails_before_payload_acceptance() -> None:
    frame = serialize_frame(OP_BINARY, b"x" * 5, mask=True)

    with pytest.raises(ProtocolError, match="websocket frame exceeds configured max payload size"):
        parse_frame_bytes(frame, expect_masked=True, max_payload_size=4)


async def _cancellation_resistant_task(release: asyncio.Event) -> None:
    try:
        await asyncio.sleep(60)
    except asyncio.CancelledError:
        await release.wait()


async def _exercise_bounded_cancellation_reports_pending_teardown() -> None:
    release = asyncio.Event()
    task = asyncio.create_task(_cancellation_resistant_task(release))
    await asyncio.sleep(0)

    result = await cancel_many_bounded([task], timeout=0.01)

    assert result.timed_out is True
    assert result.pending == 1
    assert result.completed == 0
    release.set()
    await asyncio.wait_for(task, timeout=1.0)


def test_bounded_cancellation_reports_pending_teardown() -> None:
    asyncio.run(_exercise_bounded_cancellation_reports_pending_teardown())


async def _exercise_taskset_bounded_cancellation_uses_same_teardown_contract() -> None:
    release = asyncio.Event()
    taskset = TaskSet()
    task = asyncio.create_task(_cancellation_resistant_task(release))
    taskset.add(task)
    await asyncio.sleep(0)

    result = await taskset.cancel_all_bounded(timeout=0.01)

    assert result.timed_out is True
    assert result.pending == 1
    release.set()
    await asyncio.wait_for(task, timeout=1.0)


def test_taskset_bounded_cancellation_uses_same_teardown_contract() -> None:
    asyncio.run(_exercise_taskset_bounded_cancellation_uses_same_teardown_contract())


def test_dos_warning_event_shape_is_stable_and_structured() -> None:
    event = dos_warning(
        surface="http3",
        reason="parse-buffer-limit-exceeded",
        action="reset-stream",
        resource="request.parse_buffer",
        limit=8,
        observed=9,
    )

    assert event.name == DOS_WARNING_EVENT
    assert event.attrs == {
        "surface": "http3",
        "reason": "parse-buffer-limit-exceeded",
        "action": "reset-stream",
        "resource": "request.parse_buffer",
        "limit": 8,
        "observed": 9,
    }


def test_dos_resilience_is_governed_in_generated_ssot() -> None:
    from tools.ssot_sync import build_registry

    registry = build_registry()
    features = {row["id"]: row for row in registry["features"]}
    claims = {row["id"]: row for row in registry["claims"]}
    tests = {row["id"]: row for row in registry["tests"]}
    evidence = {row["id"]: row for row in registry["evidence"]}
    specs = {row["id"]: row for row in registry["specs"]}
    boundaries = {row["id"]: row for row in registry["boundaries"]}
    profiles = {row["id"]: row for row in registry["profiles"]}

    feature = features["feat:dos-resilience-runtime"]
    assert feature["implementation_status"] == "implemented"
    assert feature["plan"]["slot"] == "availability-resilience"
    assert {"spc:2050", "spc:2003", "spc:2004", "spc:2010"} <= set(feature["spec_ids"])
    assert "spc:2050" in specs
    assert "clm:dos-resilience-runtime-implemented" in feature["claim_ids"]
    assert "tst:dos-resilience-runtime" in feature["test_ids"]
    assert claims["clm:dos-resilience-runtime-implemented"]["tier"] == "T3"
    assert tests["tst:dos-resilience-runtime"]["path"] == "tests/test_dos_resilience.py"
    assert evidence["evd:dos-resilience-runtime-pytest"]["path"] == "tests/test_dos_resilience.py"
    assert features["feat:h11-oversized-request-head-rejection"]["implementation_status"] == "implemented"
    assert "tst:h11-oversized-request-head-rejection" in features[
        "feat:h11-oversized-request-head-rejection"
    ]["test_ids"]
    assert tests["tst:h11-oversized-request-head-rejection"]["path"] == "tests/test_dos_resilience.py"
    assert features["feat:websocket-oversized-upgrade-head-rejection"]["implementation_status"] == "implemented"
    assert "tst:websocket-oversized-upgrade-head-rejection" in features[
        "feat:websocket-oversized-upgrade-head-rejection"
    ]["test_ids"]
    assert tests["tst:websocket-oversized-upgrade-head-rejection"]["path"] == "tests/test_dos_resilience.py"
    assert profiles["prf:denial-of-service-resilience"]["feature_ids"] == [
        "feat:dos-resilience-runtime",
        "feat:h11-oversized-request-head-rejection",
        "feat:websocket-oversized-upgrade-head-rejection",
    ]
    assert profiles["prf:denial-of-service-resilience"]["claim_tier"] == "T3"
    assert boundaries["bnd:availability-abuse-resilience"]["feature_ids"] == [
        "feat:dos-resilience-runtime",
        "feat:h11-oversized-request-head-rejection",
        "feat:websocket-oversized-upgrade-head-rejection",
    ]
    assert boundaries["bnd:availability-abuse-resilience"]["profile_ids"] == [
        "prf:denial-of-service-resilience"
    ]
