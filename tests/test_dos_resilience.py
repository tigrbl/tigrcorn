from __future__ import annotations

import asyncio

from tigrcorn.availability import DOS_WARNING_EVENT, dos_warning
from tigrcorn.protocols.http3.codec import H3_EXCESSIVE_LOAD, HTTP3StreamError
from tigrcorn.protocols.http3.streams import HTTP3ConnectionCore
from tigrcorn.scheduler.cancellation import cancel_many_bounded
from tigrcorn.scheduler.tasks import TaskSet
import pytest


def test_http3_request_parse_buffer_exhaustion_fails_closed() -> None:
    core = HTTP3ConnectionCore(role="server", max_request_parse_buffer_size=8)

    with pytest.raises(HTTP3StreamError) as exc_info:
        core.receive_stream_data(0, b"\x01" * 9, fin=False)

    assert exc_info.value.error_code == H3_EXCESSIVE_LOAD
    request = core.get_request(0)
    assert request.state.abandoned is True
    assert request.state.parse_buffer == bytearray()


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
    assert boundaries["bnd:availability-abuse-resilience"]["feature_ids"] == ["feat:dos-resilience-runtime"]
