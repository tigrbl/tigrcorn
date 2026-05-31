from __future__ import annotations

from tests.contract_closure_assertions import ContractClosureAssertions


class ContractIllegalEventOrderRejectionTests(ContractClosureAssertions):
    def test_illegal_event_order_rejection_contract(self) -> None:
        self.assert_illegal_event_order_rejection()
