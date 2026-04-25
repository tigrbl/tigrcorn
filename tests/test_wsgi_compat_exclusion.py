from __future__ import annotations

from tests.contract_closure_assertions import ContractClosureAssertions


class WSGICompatExclusionTests(ContractClosureAssertions):
    def test_wsgi_compat_exclusion_contract(self) -> None:
        self.assert_compat_exclusion('wsgi')
