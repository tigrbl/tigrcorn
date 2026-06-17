import pytest


pytestmark = pytest.mark.skip(reason="planned SSOT coverage for WebTransport over HTTP/2 capsules")


def test_webtransport_h2_capsule_codec_roundtrip():
    """Planned coverage for tst:webtransport-h2-capsule-codec-roundtrip."""


def test_webtransport_h2_malformed_capsule_fail_closed():
    """Planned coverage for tst:webtransport-h2-malformed-capsule-fail-closed."""


def test_webtransport_h2_bidi_stream_capsule_roundtrip():
    """Planned coverage for tst:webtransport-h2-bidi-stream-capsule-roundtrip."""


def test_webtransport_h2_unidi_stream_capsule_roundtrip():
    """Planned coverage for tst:webtransport-h2-unidi-stream-capsule-roundtrip."""


def test_webtransport_h2_reset_stop_sending_capsules():
    """Planned coverage for tst:webtransport-h2-reset-stop-sending-capsules."""


def test_webtransport_h2_cross_session_stream_rejected():
    """Planned coverage for tst:webtransport-h2-cross-session-stream-rejected."""


def test_webtransport_h2_datagram_capsule_roundtrip():
    """Planned coverage for tst:webtransport-h2-datagram-capsule-roundtrip."""


def test_webtransport_h2_datagram_budget_and_orphan_rejection():
    """Planned coverage for tst:webtransport-h2-datagram-budget-and-orphan-rejection."""
