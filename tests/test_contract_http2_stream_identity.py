from __future__ import annotations

from tests.contract_closure_assertions import ContractClosureAssertions


class ContractHTTP2StreamIdentityTests(ContractClosureAssertions):
    def test_http2_stream_identity_contract(self) -> None:
        self.assert_stream_identity('http2')
