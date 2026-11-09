from __future__ import annotations

import pytest

from tigrcorn.contract import endpoint_metadata
from tigrcorn.errors import ProtocolError
from tests.contract_closure_assertions import ContractClosureAssertions


class ContractUDSEndpointMetadataTests(ContractClosureAssertions):
    def test_uds_endpoint_metadata_contract(self) -> None:
        self.assert_endpoint_metadata('uds')


def test_uds_endpoint_preserves_socket_path_only() -> None:
    endpoint = endpoint_metadata("uds", address="/tmp/tigrcorn.sock")

    assert endpoint.as_dict() == {"kind": "uds", "address": "/tmp/tigrcorn.sock"}


@pytest.mark.parametrize(
    "fields",
    [
        {"address": ""},
        {"address": "   "},
        {"address": "/tmp/tigrcorn.sock", "port": 8000},
        {"address": "/tmp/tigrcorn.sock", "fd": 3},
    ],
)
def test_uds_endpoint_fails_closed_for_lossy_or_irrelevant_fields(fields: dict[str, object]) -> None:
    with pytest.raises(ProtocolError):
        endpoint_metadata("uds", **fields)
