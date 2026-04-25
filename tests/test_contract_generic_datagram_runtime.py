from __future__ import annotations

from tests.contract_closure_assertions import ContractClosureAssertions


class ContractGenericDatagramRuntimeTests(ContractClosureAssertions):
    def test_generic_datagram_runtime_contract(self) -> None:
        self.assert_generic_datagram_runtime()
