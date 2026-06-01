from __future__ import annotations

import pytest

from tigrcorn.contract import endpoint_metadata
from tigrcorn.errors import ProtocolError
from tests.contract_closure_assertions import ContractClosureAssertions


class ContractPipeEndpointMetadataTests(ContractClosureAssertions):
    def test_pipe_endpoint_metadata_contract(self) -> None:
        self.assert_endpoint_metadata('pipe')


def test_pipe_endpoint_preserves_pipe_name_only() -> None:
    endpoint = endpoint_metadata("pipe", pipe_name=r"\\.\pipe\tigrcorn")

    assert endpoint.as_dict() == {"kind": "pipe", "pipe_name": r"\\.\pipe\tigrcorn"}


@pytest.mark.parametrize(
    "fields",
    [
        {"pipe_name": ""},
        {"pipe_name": "   "},
        {"pipe_name": r"\\.\pipe\tigrcorn", "address": "not-a-socket"},
        {"pipe_name": r"\\.\pipe\tigrcorn", "fd": 3},
    ],
)
def test_pipe_endpoint_fails_closed_for_lossy_or_irrelevant_fields(fields: dict[str, object]) -> None:
    with pytest.raises(ProtocolError):
        endpoint_metadata("pipe", **fields)
