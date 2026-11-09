from __future__ import annotations

from tests.contract_closure_assertions import ContractClosureAssertions


class ASGI3SecurityMetadataExtensionTests(ContractClosureAssertions):
    def test_asgi3_security_metadata_extension_contract(self) -> None:
        self.assert_asgi3_extension('tigrcorn.security')
