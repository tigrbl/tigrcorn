from __future__ import annotations

from tests.contract_closure_assertions import ContractClosureAssertions


class WebTransportH3QUICCompletionEventsTests(ContractClosureAssertions):
    def test_webtransport_completion_event_contract(self) -> None:
        self.assert_webtransport_completion_events()
