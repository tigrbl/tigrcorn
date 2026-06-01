from __future__ import annotations

import pytest

from tigrcorn.contract import endpoint_metadata
from tigrcorn.errors import ProtocolError
from tests.contract_closure_assertions import ContractClosureAssertions


class ContractInprocEndpointMetadataTests(ContractClosureAssertions):
    def test_inproc_endpoint_metadata_contract(self) -> None:
        self.assert_endpoint_metadata('inproc')


def test_inproc_endpoint_preserves_inproc_name_only() -> None:
    endpoint = endpoint_metadata("inproc", inproc_name="worker-1")

    assert endpoint.as_dict() == {"kind": "inproc", "inproc_name": "worker-1"}


@pytest.mark.parametrize(
    "fields",
    [
        {"inproc_name": ""},
        {"inproc_name": "   "},
        {"inproc_name": "worker-1", "address": "127.0.0.1"},
        {"inproc_name": "worker-1", "pipe_name": r"\\.\pipe\wrong"},
    ],
)
def test_inproc_endpoint_fails_closed_for_lossy_or_irrelevant_fields(fields: dict[str, object]) -> None:
    with pytest.raises(ProtocolError):
        endpoint_metadata("inproc", **fields)
