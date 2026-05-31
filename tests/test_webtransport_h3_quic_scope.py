from __future__ import annotations

from tests.contract_closure_assertions import ContractClosureAssertions


class WebTransportH3QUICScopeTests(ContractClosureAssertions):
    def test_webtransport_h3_quic_scope_contract(self) -> None:
        self.assert_webtransport_scope()
