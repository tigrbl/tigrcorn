from __future__ import annotations

from tests.contract_closure_assertions import ContractClosureAssertions


class ContractWebTransportSessionIdentityTests(ContractClosureAssertions):
    def test_webtransport_session_identity_contract(self) -> None:
        self.assert_stream_identity('webtransport-session')
