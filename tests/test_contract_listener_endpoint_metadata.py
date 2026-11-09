from __future__ import annotations

import pytest

from tigrcorn.contract import endpoint_metadata
from tigrcorn.errors import ProtocolError
from tests.contract_closure_assertions import ContractClosureAssertions


class ContractListenerEndpointMetadataTests(ContractClosureAssertions):
    def test_listener_endpoint_metadata_contract(self) -> None:
        self.assert_endpoint_metadata('tcp')


def test_tcp_listener_endpoint_preserves_only_address_and_port() -> None:
    endpoint = endpoint_metadata("tcp", address="127.0.0.1", port=8443)

    assert endpoint.as_dict() == {"kind": "tcp", "address": "127.0.0.1", "port": 8443}


@pytest.mark.parametrize(
    "fields",
    [
        {"address": "", "port": 8443},
        {"address": "   ", "port": 8443},
        {"address": "127.0.0.1", "port": True},
        {"address": "127.0.0.1", "port": 8443, "fd": 3},
        {"address": "127.0.0.1", "port": 8443, "pipe_name": r"\\.\pipe\wrong"},
    ],
)
def test_tcp_listener_endpoint_fails_closed_for_lossy_or_irrelevant_fields(fields: dict[str, object]) -> None:
    with pytest.raises(ProtocolError):
        endpoint_metadata("tcp", **fields)
