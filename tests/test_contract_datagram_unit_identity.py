from __future__ import annotations

from tests.contract_closure_assertions import ContractClosureAssertions


class ContractDatagramUnitIdentityTests(ContractClosureAssertions):
    def test_datagram_unit_identity_contract(self) -> None:
        self.assert_datagram_identity()
