from __future__ import annotations

from tests.contract_closure_assertions import ContractClosureAssertions


class ContractWebTransportStreamIdentityTests(ContractClosureAssertions):
    def test_webtransport_stream_identity_contract(self) -> None:
        self.assert_stream_identity('webtransport-stream')
