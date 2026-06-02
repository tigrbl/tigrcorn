from __future__ import annotations

from tests.support.client_session_matrix import sequential_pair
from tigrcorn_protocols.client_session_coverage import ProtocolCarrier, SessionScope


def test_http1_sequential_requests_are_request_scoped() -> None:
    harness = sequential_pair(ProtocolCarrier.HTTP1, SessionScope.REQUEST_SCOPED)
    assert all(event["session_scope"] == "request_scoped" for event in harness.events)
    assert harness.sessions["session-a"].payloads == ["a-1"]
    assert harness.sessions["session-b"].payloads == ["b-1"]
