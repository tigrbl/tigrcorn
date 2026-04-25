from __future__ import annotations

from tests.contract_closure_assertions import ContractClosureAssertions


class ContractListenerEndpointMetadataTests(ContractClosureAssertions):
    def test_listener_endpoint_metadata_contract(self) -> None:
        self.assert_endpoint_metadata('tcp')
