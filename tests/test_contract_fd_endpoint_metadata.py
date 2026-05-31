from __future__ import annotations

from tests.contract_closure_assertions import ContractClosureAssertions


class ContractFDEndpointMetadataTests(ContractClosureAssertions):
    def test_fd_endpoint_metadata_contract(self) -> None:
        self.assert_endpoint_metadata('fd')
