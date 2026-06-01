from __future__ import annotations

from tigrcorn.contract import validate_event_order, webtransport_accept, webtransport_close, webtransport_connect, webtransport_stream_send
from tigrcorn.errors import ProtocolError

from tests.contract_closure_assertions import ContractClosureAssertions


class ContractIllegalEventOrderRejectionTests(ContractClosureAssertions):
    def test_illegal_event_order_rejection_contract(self) -> None:
        self.assert_illegal_event_order_rejection()

    def test_rejects_events_after_terminal_close(self) -> None:
        with self.assertRaises(ProtocolError):
            validate_event_order(
                [
                    webtransport_connect("s1"),
                    webtransport_accept("s1"),
                    webtransport_close("s1"),
                    webtransport_stream_send("s1", "st1", b"late"),
                ],
                required_first="webtransport.connect",
                terminal_prefixes=("webtransport.disconnect", "webtransport.close"),
            )

    def test_rejects_duplicate_open_and_malformed_event_type(self) -> None:
        with self.assertRaises(ProtocolError):
            validate_event_order(
                [webtransport_connect("s1"), webtransport_connect("s1")],
                required_first="webtransport.connect",
                terminal_prefixes=("webtransport.disconnect", "webtransport.close"),
            )
        with self.assertRaises(ProtocolError):
            validate_event_order(
                [webtransport_connect("s1"), {"type": ""}],
                required_first="webtransport.connect",
                terminal_prefixes=("webtransport.disconnect", "webtransport.close"),
            )
