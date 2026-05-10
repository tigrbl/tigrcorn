import pytest


@pytest.mark.skip(reason="RFC 9113 gap placeholder: content-length mismatch rejection is not implemented yet")
def test_rfc9113_http2_rejects_content_length_mismatch() -> None:
    raise AssertionError("placeholder")


@pytest.mark.skip(reason="RFC 9113 gap placeholder: malformed field-value rejection is not implemented yet")
def test_rfc9113_http2_rejects_malformed_field_values() -> None:
    raise AssertionError("placeholder")


@pytest.mark.skip(reason="RFC 9113 gap placeholder: Host and :authority mismatch rejection is not implemented yet")
def test_rfc9113_http2_rejects_host_authority_mismatch() -> None:
    raise AssertionError("placeholder")


@pytest.mark.skip(reason="RFC 9113 gap placeholder: malformed request-target rejection is not implemented yet")
def test_rfc9113_http2_rejects_malformed_request_targets() -> None:
    raise AssertionError("placeholder")


@pytest.mark.skip(reason="RFC 9113 gap placeholder: unsafe server-push method rejection is not implemented yet")
def test_rfc9113_http2_rejects_unsafe_server_push_methods() -> None:
    raise AssertionError("placeholder")
