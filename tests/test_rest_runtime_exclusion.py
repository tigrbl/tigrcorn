from __future__ import annotations

from tests.contract_closure_assertions import ContractClosureAssertions


class RESTRuntimeExclusionTests(ContractClosureAssertions):
    def test_rest_runtime_exclusion_contract(self) -> None:
        self.assert_runtime_exclusion('rest')
