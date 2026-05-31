from __future__ import annotations

from tests.contract_closure_assertions import ContractClosureAssertions


class ContractHTTP3StreamIdentityTests(ContractClosureAssertions):
    def test_http3_stream_identity_contract(self) -> None:
        self.assert_stream_identity('http3')
