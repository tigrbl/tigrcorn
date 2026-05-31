from __future__ import annotations

from tests.contract_closure_assertions import ContractClosureAssertions


class ContractInprocEndpointMetadataTests(ContractClosureAssertions):
    def test_inproc_endpoint_metadata_contract(self) -> None:
        self.assert_endpoint_metadata('inproc')
