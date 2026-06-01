from __future__ import annotations

import pytest

from tigrcorn.contract import transport_identity
from tigrcorn.errors import ProtocolError
from tests.contract_closure_assertions import ContractClosureAssertions


class ContractTCPConnectionIdentityTests(ContractClosureAssertions):
    def test_tcp_connection_identity_contract(self) -> None:
        self.assert_connection_identity('tcp')


def test_tcp_connection_identity_preserves_peer_local_and_metadata() -> None:
    identity = transport_identity("tcp", "conn-1", peer="client", local="server", metadata={"alpn": "h2"})

    assert identity.as_dict() == {
        "kind": "tcp",
        "connection_id": "conn-1",
        "alpn": "h2",
        "peer": "client",
        "local": "server",
    }


@pytest.mark.parametrize(
    "kwargs",
    [
        {"kind": "tcp", "connection_id": ""},
        {"kind": "tcp", "connection_id": "   "},
        {"kind": "tcp", "connection_id": "conn-1", "peer": ""},
        {"kind": "tcp", "connection_id": "conn-1", "local": "   "},
        {"kind": "tcp", "connection_id": "conn-1", "metadata": {"alpn": ""}},
        {"kind": "tcp", "connection_id": "conn-1", "unexpected": True},
    ],
)
def test_tcp_connection_identity_fails_closed_for_lossy_or_irrelevant_fields(kwargs: dict[str, object]) -> None:
    with pytest.raises(ProtocolError):
        transport_identity(**kwargs)
