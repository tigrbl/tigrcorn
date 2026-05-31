from __future__ import annotations

from tests.contract_closure_assertions import ContractClosureAssertions


class ContractUDSEndpointMetadataTests(ContractClosureAssertions):
    def test_uds_endpoint_metadata_contract(self) -> None:
        self.assert_endpoint_metadata('uds')
