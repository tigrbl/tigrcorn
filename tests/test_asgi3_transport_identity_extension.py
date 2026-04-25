from __future__ import annotations

from tests.contract_closure_assertions import ContractClosureAssertions


class ASGI3TransportIdentityExtensionTests(ContractClosureAssertions):
    def test_asgi3_transport_identity_extension_contract(self) -> None:
        self.assert_asgi3_extension('tigrcorn.transport')
