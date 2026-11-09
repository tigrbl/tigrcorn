from __future__ import annotations

import pytest

from tigrcorn.contract import datagram_identity, validate_stream_identity
from tigrcorn.errors import ProtocolError
from tests.contract_closure_assertions import ContractClosureAssertions


class ContractDatagramUnitIdentityTests(ContractClosureAssertions):
    def test_datagram_unit_identity_contract(self) -> None:
        self.assert_datagram_identity()


def test_datagram_unit_identity_preserves_connection_session_and_datagram_ids() -> None:
    identity = datagram_identity("conn-1", "dgram-1", session_id="session-1")

    assert identity.as_dict() == {
        "kind": "datagram",
        "connection_id": "conn-1",
        "stream_id": "dgram-1",
        "session_id": "session-1",
        "datagram_id": "dgram-1",
    }


@pytest.mark.parametrize(
    "args",
    [
        ("", "dgram-1"),
        ("   ", "dgram-1"),
        ("conn-1", ""),
        ("conn-1", "   "),
    ],
)
def test_datagram_unit_identity_fails_closed_for_lossy_required_ids(args: tuple[str, str]) -> None:
    with pytest.raises(ProtocolError):
        datagram_identity(*args)


def test_datagram_unit_identity_rejects_lossy_session_id() -> None:
    with pytest.raises(ProtocolError):
        datagram_identity("conn-1", "dgram-1", session_id="   ")


def test_datagram_unit_identity_rejects_mismatched_stream_and_datagram_ids() -> None:
    identity = datagram_identity("conn-1", "dgram-1")
    corrupted = type(identity)(
        kind="datagram",
        connection_id="conn-1",
        stream_id="stream-1",
        datagram_id="dgram-1",
    )

    with pytest.raises(ProtocolError, match="stream_id"):
        validate_stream_identity(corrupted)
