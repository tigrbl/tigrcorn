from __future__ import annotations

from tests.contract_closure_assertions import ContractClosureAssertions


class ContractRESTBindingClassificationTests(ContractClosureAssertions):
    def test_rest_binding_classification_contract(self) -> None:
        self.assert_binding_classification('rest')
