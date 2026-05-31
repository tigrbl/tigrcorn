from __future__ import annotations

from tests.contract_closure_assertions import ContractClosureAssertions


class JSONRPCRuntimeExclusionTests(ContractClosureAssertions):
    def test_json_rpc_runtime_exclusion_contract(self) -> None:
        self.assert_runtime_exclusion('json-rpc')
