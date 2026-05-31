from __future__ import annotations

from tests.contract_closure_assertions import ContractClosureAssertions


class ContractLossyMetadataRejectionTests(ContractClosureAssertions):
    def test_lossy_metadata_rejection_contract(self) -> None:
        self.assert_lossy_metadata_rejection()
