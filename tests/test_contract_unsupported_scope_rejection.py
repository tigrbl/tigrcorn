from __future__ import annotations

from tests.contract_closure_assertions import ContractClosureAssertions


class ContractUnsupportedScopeRejectionTests(ContractClosureAssertions):
    def test_unsupported_scope_rejection_contract(self) -> None:
        self.assert_unsupported_scope_rejection()
