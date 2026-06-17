from __future__ import annotations

import pytest

from tigrcorn.contract import CompletionLevel, CompletionStatus, emit_complete
from tigrcorn.errors import ProtocolError
from tests.contract_closure_assertions import ContractClosureAssertions


class ContractEmitCompletionEventsTests(ContractClosureAssertions):
    def test_emit_completion_event_contract(self) -> None:
        self.assert_completion_event()


def test_emit_completion_event_accepts_canonical_enums_and_detail() -> None:
    event = emit_complete(
        "unit-1",
        level=CompletionLevel.ACCEPTED_BY_RUNTIME,
        status=CompletionStatus.REJECTED,
        detail="queue closed",
    )

    assert event == {
        "type": "transport.emit.complete",
        "unit_id": "unit-1",
        "level": "accepted_by_runtime",
        "status": "rejected",
        "detail": "queue closed",
    }


@pytest.mark.parametrize(
    ("alias", "expected"),
    [
        ("buffered", "accepted_by_runtime"),
        ("accepted", "accepted_by_runtime"),
        ("flushed", "flushed_to_transport"),
        ("transport", "flushed_to_transport"),
        ("acknowledged", "peer_acknowledged"),
    ],
)
def test_emit_completion_event_normalizes_legacy_level_aliases(alias: str, expected: str) -> None:
    assert emit_complete("unit-1", level=alias)["level"] == expected


@pytest.mark.parametrize(
    "kwargs",
    [
        {"unit_id": ""},
        {"unit_id": "   "},
        {"unit_id": "unit-1", "level": "wire"},
        {"unit_id": "unit-1", "status": "maybe"},
    ],
)
def test_emit_completion_event_fails_closed_for_malformed_values(kwargs: dict[str, str]) -> None:
    with pytest.raises(ProtocolError):
        emit_complete(**kwargs)
