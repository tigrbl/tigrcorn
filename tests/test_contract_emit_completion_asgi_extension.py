from __future__ import annotations

from tests.contract_closure_assertions import ContractClosureAssertions


class ContractEmitCompletionASGIExtensionTests(ContractClosureAssertions):
    def test_emit_completion_asgi_extension_contract(self) -> None:
        self.assert_asgi3_extension('tigrcorn.emit_completion')
