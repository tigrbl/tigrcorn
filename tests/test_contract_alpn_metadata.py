from __future__ import annotations

from tests.contract_closure_assertions import ContractClosureAssertions


class ContractALPNMetadataTests(ContractClosureAssertions):
    def test_alpn_metadata_contract(self) -> None:
        self.assert_security_metadata('alpn')
