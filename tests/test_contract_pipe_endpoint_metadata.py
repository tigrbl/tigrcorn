from __future__ import annotations

from tests.contract_closure_assertions import ContractClosureAssertions


class ContractPipeEndpointMetadataTests(ContractClosureAssertions):
    def test_pipe_endpoint_metadata_contract(self) -> None:
        self.assert_endpoint_metadata('pipe')
