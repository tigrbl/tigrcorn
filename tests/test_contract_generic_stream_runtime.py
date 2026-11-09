from __future__ import annotations

import pytest

from tigrcorn.contract import GenericStreamRuntime, stream_receive, stream_send, validate_stream_event
from tigrcorn.errors import ProtocolError
from tests.contract_closure_assertions import ContractClosureAssertions


class ContractGenericStreamRuntimeTests(ContractClosureAssertions):
    def test_generic_stream_runtime_contract(self) -> None:
        self.assert_generic_stream_runtime()


def test_generic_stream_runtime_preserves_order_and_completion() -> None:
    runtime = GenericStreamRuntime()

    first = runtime.receive("stream-1", b"hello", more=True)
    second = runtime.send("stream-1", b"world", more=True)
    complete = runtime.complete("stream-1", level="accepted", status="ok")

    assert first["type"] == "transport.stream.receive"
    assert second["type"] == "transport.stream.send"
    assert complete == {
        "type": "transport.emit.complete",
        "unit_id": "stream-1",
        "emit_id": "stream-1",
        "level": "accepted_by_runtime",
        "status": "ok",
    }
    assert [event["type"] for event in runtime.events] == [
        "transport.stream.receive",
        "transport.stream.send",
        "transport.emit.complete",
    ]


def test_generic_stream_runtime_rejects_events_after_completion() -> None:
    runtime = GenericStreamRuntime()
    runtime.receive("stream-1", b"hello")
    runtime.complete("stream-1")

    with pytest.raises(ProtocolError, match="already completed"):
        runtime.send("stream-1", b"late")


def test_generic_stream_event_validation_accepts_receive_and_send() -> None:
    validate_stream_event(stream_receive("stream-1", b"in", more=True))
    validate_stream_event(stream_send("stream-1", b"out"))


@pytest.mark.parametrize(
    "event",
    [
        {"type": "transport.stream.receive", "stream_id": "", "data": b"x"},
        {"type": "transport.stream.receive", "stream_id": "s1", "data": "x"},
        {"type": "transport.stream.receive", "stream_id": "s1", "data": b"x", "more": "yes"},
        {"type": "transport.datagram.receive", "stream_id": "s1", "data": b"x"},
    ],
)
def test_generic_stream_event_validation_fails_closed(event: dict[str, object]) -> None:
    with pytest.raises(ProtocolError):
        validate_stream_event(event)


def test_generic_stream_factory_rejects_malformed_payloads() -> None:
    with pytest.raises(ProtocolError, match="unit_id"):
        stream_receive("", b"x")
    with pytest.raises(ProtocolError, match="bytes"):
        stream_send("stream-1", "x")  # type: ignore[arg-type]
    with pytest.raises(ProtocolError, match="boolean"):
        stream_send("stream-1", b"x", more=1)  # type: ignore[arg-type]
