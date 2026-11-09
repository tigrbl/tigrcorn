from __future__ import annotations

from tests.contract_closure_assertions import ContractClosureAssertions


class WebTransportH3QUICDatagramEventsTests(ContractClosureAssertions):
    def test_webtransport_datagram_event_contract(self) -> None:
        self.assert_webtransport_datagram_events()
