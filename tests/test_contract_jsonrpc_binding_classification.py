from __future__ import annotations

from tests.contract_closure_assertions import ContractClosureAssertions


class ContractJSONRPCBindingClassificationTests(ContractClosureAssertions):
    def test_jsonrpc_binding_classification_contract(self) -> None:
        self.assert_binding_classification('jsonrpc')
