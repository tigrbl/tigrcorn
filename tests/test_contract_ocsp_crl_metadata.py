from __future__ import annotations

from tests.contract_closure_assertions import ContractClosureAssertions


class ContractOCSPCRLMetadataTests(ContractClosureAssertions):
    def test_ocsp_crl_metadata_contract(self) -> None:
        self.assert_security_metadata('ocsp')
