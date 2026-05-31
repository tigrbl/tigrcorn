from __future__ import annotations

from tests.contract_closure_assertions import ContractClosureAssertions


class ContractInvalidEndpointMetadataRejectionTests(ContractClosureAssertions):
    def test_invalid_endpoint_metadata_rejection_contract(self) -> None:
        self.assert_invalid_endpoint_metadata_rejection()
