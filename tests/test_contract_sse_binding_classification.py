from __future__ import annotations

from tests.contract_closure_assertions import ContractClosureAssertions


class ContractSSEBindingClassificationTests(ContractClosureAssertions):
    def test_sse_binding_classification_contract(self) -> None:
        self.assert_binding_classification('sse')
