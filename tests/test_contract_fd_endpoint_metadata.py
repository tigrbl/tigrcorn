from __future__ import annotations

import pytest

from tigrcorn.contract import endpoint_metadata
from tigrcorn.errors import ProtocolError
from tests.contract_closure_assertions import ContractClosureAssertions


class ContractFDEndpointMetadataTests(ContractClosureAssertions):
    def test_fd_endpoint_metadata_contract(self) -> None:
        self.assert_endpoint_metadata('fd')


def test_fd_endpoint_preserves_fd_only() -> None:
    endpoint = endpoint_metadata("fd", fd=3)

    assert endpoint.as_dict() == {"kind": "fd", "fd": 3}


@pytest.mark.parametrize(
    "fields",
    [
        {"fd": True},
        {"fd": -1},
        {"fd": 3, "address": "127.0.0.1"},
        {"fd": 3, "port": 8443},
    ],
)
def test_fd_endpoint_fails_closed_for_invalid_or_irrelevant_fields(fields: dict[str, object]) -> None:
    with pytest.raises(ProtocolError):
        endpoint_metadata("fd", **fields)
