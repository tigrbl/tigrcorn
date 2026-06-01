from __future__ import annotations

import pytest

from tigrcorn.contract import transport_identity
from tigrcorn.errors import ProtocolError
from tests.contract_closure_assertions import ContractClosureAssertions


class ContractUnixConnectionIdentityTests(ContractClosureAssertions):
    def test_unix_connection_identity_contract(self) -> None:
        self.assert_connection_identity('unix')


def test_unix_connection_identity_preserves_socket_identity_metadata() -> None:
    identity = transport_identity("unix", "unix-conn-1", peer="client", local="/tmp/tigrcorn.sock")

    assert identity.as_dict() == {
        "kind": "unix",
        "connection_id": "unix-conn-1",
        "peer": "client",
        "local": "/tmp/tigrcorn.sock",
    }


@pytest.mark.parametrize(
    "kwargs",
    [
        {"kind": "unix", "connection_id": ""},
        {"kind": "unix", "connection_id": "conn-1", "peer": "   "},
        {"kind": "unix", "connection_id": "conn-1", "metadata": []},
        {"kind": "unix", "connection_id": "conn-1", "metadata": {"socket": "   "}},
        {"kind": "unix", "connection_id": "conn-1", "stream_id": "not-a-connection-field"},
    ],
)
def test_unix_connection_identity_fails_closed_for_lossy_or_irrelevant_fields(kwargs: dict[str, object]) -> None:
    with pytest.raises(ProtocolError):
        transport_identity(**kwargs)
