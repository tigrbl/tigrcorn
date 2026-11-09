from __future__ import annotations

from tests.contract_closure_assertions import ContractClosureAssertions


class ContractDatagramFlowControlMappingTests(ContractClosureAssertions):
    def test_datagram_flow_control_mapping_contract(self) -> None:
        self.assert_generic_datagram_runtime()
