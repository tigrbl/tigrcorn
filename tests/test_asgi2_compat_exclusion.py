from __future__ import annotations

from tests.contract_closure_assertions import ContractClosureAssertions


class ASGI2CompatExclusionTests(ContractClosureAssertions):
    def test_asgi2_compat_exclusion_contract(self) -> None:
        self.assert_compat_exclusion('asgi2')
