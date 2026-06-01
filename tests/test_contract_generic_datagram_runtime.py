from __future__ import annotations

import pytest

from tigrcorn.contract import GenericDatagramRuntime, datagram_receive, datagram_send, validate_datagram_event
from tigrcorn.errors import ProtocolError
from tests.contract_closure_assertions import ContractClosureAssertions


class ContractGenericDatagramRuntimeTests(ContractClosureAssertions):
    def test_generic_datagram_runtime_contract(self) -> None:
        self.assert_generic_datagram_runtime()


def test_generic_datagram_runtime_preserves_independent_units_and_completion() -> None:
    runtime = GenericDatagramRuntime()

    received = runtime.receive("dgram-1", b"in")
    sent = runtime.send("dgram-2", b"out", flow_controlled=True)
    complete = runtime.complete("dgram-1", level="transport", status="ok")

    assert received == {
        "type": "transport.datagram.receive",
        "datagram_id": "dgram-1",
        "data": b"in",
        "flow_controlled": False,
    }
    assert sent["flow_controlled"] is True
    assert complete["type"] == "transport.emit.complete"
    assert complete["unit_id"] == "dgram-1"
    assert [event["type"] for event in runtime.events] == [
        "transport.datagram.receive",
        "transport.datagram.send",
        "transport.emit.complete",
    ]


def test_generic_datagram_runtime_rejects_reuse_after_completion() -> None:
    runtime = GenericDatagramRuntime()
    runtime.receive("dgram-1", b"in")
    runtime.complete("dgram-1")

    with pytest.raises(ProtocolError, match="already completed"):
        runtime.receive("dgram-1", b"late")


def test_generic_datagram_event_validation_accepts_receive_and_send() -> None:
    validate_datagram_event(datagram_receive("dgram-1", b"in"))
    validate_datagram_event(datagram_send("dgram-2", b"out", flow_controlled=True))


@pytest.mark.parametrize(
    "event",
    [
        {"type": "transport.datagram.receive", "datagram_id": "", "data": b"x"},
        {"type": "transport.datagram.receive", "datagram_id": "d1", "data": "x"},
        {"type": "transport.datagram.receive", "datagram_id": "d1", "data": b"x", "flow_controlled": "true"},
        {"type": "transport.stream.receive", "datagram_id": "d1", "data": b"x"},
    ],
)
def test_generic_datagram_event_validation_fails_closed(event: dict[str, object]) -> None:
    with pytest.raises(ProtocolError):
        validate_datagram_event(event)


def test_generic_datagram_factory_rejects_malformed_payloads() -> None:
    with pytest.raises(ProtocolError, match="unit_id"):
        datagram_receive("", b"x")
    with pytest.raises(ProtocolError, match="bytes"):
        datagram_send("dgram-1", "x")  # type: ignore[arg-type]
    with pytest.raises(ProtocolError, match="boolean"):
        datagram_send("dgram-1", b"x", flow_controlled=1)  # type: ignore[arg-type]
