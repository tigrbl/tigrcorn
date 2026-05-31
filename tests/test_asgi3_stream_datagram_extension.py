from __future__ import annotations

from tests.contract_closure_assertions import ContractClosureAssertions


class ASGI3StreamDatagramExtensionTests(ContractClosureAssertions):
    def test_asgi3_stream_datagram_extension_contract(self) -> None:
        self.assert_asgi3_extension('tigrcorn.stream')
