from __future__ import annotations

from tests.contract_closure_assertions import ContractClosureAssertions


class ContractStreamBackpressureMappingTests(ContractClosureAssertions):
    def test_stream_backpressure_mapping_contract(self) -> None:
        self.assert_generic_stream_runtime()
