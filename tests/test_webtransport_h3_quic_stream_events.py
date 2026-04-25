from __future__ import annotations

from tests.contract_closure_assertions import ContractClosureAssertions


class WebTransportH3QUICStreamEventsTests(ContractClosureAssertions):
    def test_webtransport_stream_event_contract(self) -> None:
        self.assert_webtransport_stream_events()
