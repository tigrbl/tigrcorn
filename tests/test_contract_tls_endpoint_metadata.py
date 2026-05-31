from __future__ import annotations

from tests.contract_closure_assertions import ContractClosureAssertions


class ContractTLSEndpointMetadataTests(ContractClosureAssertions):
    def test_tls_endpoint_metadata_contract(self) -> None:
        self.assert_security_metadata('tls')
