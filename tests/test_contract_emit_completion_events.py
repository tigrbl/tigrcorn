from __future__ import annotations

from tests.contract_closure_assertions import ContractClosureAssertions


class ContractEmitCompletionEventsTests(ContractClosureAssertions):
    def test_emit_completion_event_contract(self) -> None:
        self.assert_completion_event()
