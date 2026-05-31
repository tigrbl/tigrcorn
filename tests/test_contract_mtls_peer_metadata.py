from __future__ import annotations

from tests.contract_closure_assertions import ContractClosureAssertions


class ContractMTLSPeerMetadataTests(ContractClosureAssertions):
    def test_mtls_peer_metadata_contract(self) -> None:
        self.assert_security_metadata('mtls')
