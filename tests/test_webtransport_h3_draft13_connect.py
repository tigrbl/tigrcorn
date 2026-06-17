import pytest


pytestmark = pytest.mark.skip(reason="planned SSOT coverage for WebTransport over HTTP/3 draft-13 CONNECT")


def test_webtransport_h3_draft13_extended_connect_admits_session():
    """Planned coverage for tst:webtransport-h3-draft13-extended-connect-admits-session."""


def test_webtransport_h3_draft13_origin_authority_path_validation():
    """Planned coverage for tst:webtransport-h3-draft13-origin-authority-path-validation."""


def test_webtransport_h3_wt_available_protocols_request():
    """Planned coverage for tst:webtransport-h3-wt-available-protocols-request."""


def test_webtransport_h3_wt_protocol_response_selection():
    """Planned coverage for tst:webtransport-h3-wt-protocol-response-selection."""


def test_webtransport_h3_wt_protocol_invalid_selection_rejected():
    """Planned coverage for tst:webtransport-h3-wt-protocol-invalid-selection-rejected."""
