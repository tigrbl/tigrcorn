from __future__ import annotations

from tests.contract_closure_assertions import ContractClosureAssertions


class RSGICompatExclusionTests(ContractClosureAssertions):
    def test_rsgi_compat_exclusion_contract(self) -> None:
        self.assert_compat_exclusion('rsgi')
