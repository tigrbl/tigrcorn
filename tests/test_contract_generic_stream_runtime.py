from __future__ import annotations

from tests.contract_closure_assertions import ContractClosureAssertions


class ContractGenericStreamRuntimeTests(ContractClosureAssertions):
    def test_generic_stream_runtime_contract(self) -> None:
        self.assert_generic_stream_runtime()
