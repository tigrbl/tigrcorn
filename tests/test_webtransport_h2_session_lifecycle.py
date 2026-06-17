import pytest


pytestmark = pytest.mark.skip(reason="planned SSOT coverage for WebTransport over HTTP/2 session lifecycle")


def test_webtransport_h2_connect_close_terminates_session():
    """Planned coverage for tst:webtransport-h2-connect-close-terminates-session."""


def test_webtransport_h2_close_session_capsule():
    """Planned coverage for tst:webtransport-h2-close-session-capsule."""


def test_webtransport_h2_drain_session_capsule():
    """Planned coverage for tst:webtransport-h2-drain-session-capsule."""


def test_webtransport_h2_post_close_traffic_rejected():
    """Planned coverage for tst:webtransport-h2-post-close-traffic-rejected."""
