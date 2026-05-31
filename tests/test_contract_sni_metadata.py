from __future__ import annotations

from tests.contract_closure_assertions import ContractClosureAssertions


class ContractSNIMetadataTests(ContractClosureAssertions):
    def test_sni_metadata_contract(self) -> None:
        self.assert_security_metadata('sni')
