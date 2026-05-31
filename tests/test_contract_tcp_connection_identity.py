from __future__ import annotations

from tests.contract_closure_assertions import ContractClosureAssertions


class ContractTCPConnectionIdentityTests(ContractClosureAssertions):
    def test_tcp_connection_identity_contract(self) -> None:
        self.assert_connection_identity('tcp')
