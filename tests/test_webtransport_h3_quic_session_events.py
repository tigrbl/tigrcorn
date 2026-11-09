from __future__ import annotations

from tests.contract_closure_assertions import ContractClosureAssertions


class WebTransportH3QUICSessionEventsTests(ContractClosureAssertions):
    def test_webtransport_session_event_contract(self) -> None:
        self.assert_webtransport_session_events()
