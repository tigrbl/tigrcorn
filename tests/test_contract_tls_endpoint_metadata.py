from __future__ import annotations

import pytest

from tigrcorn.contract import security_metadata
from tigrcorn.errors import ProtocolError
from tests.contract_closure_assertions import ContractClosureAssertions


class ContractTLSEndpointMetadataTests(ContractClosureAssertions):
    def test_tls_endpoint_metadata_contract(self) -> None:
        self.assert_security_metadata('tls')


def test_tls_endpoint_metadata_preserves_tls_flag_only_when_true() -> None:
    assert security_metadata(tls=True).as_dict() == {"tls": True}
    assert security_metadata(tls=False).as_dict() == {}


@pytest.mark.parametrize(
    "kwargs",
    [
        {"tls": "true"},
        {"mtls": "false"},
        {"mtls": True},
        {"tls": True, "mtls": True},
        {"tls": True, "unexpected": True},
    ],
)
def test_tls_endpoint_metadata_fails_closed_for_invalid_values(kwargs: dict[str, object]) -> None:
    with pytest.raises(ProtocolError):
        security_metadata(**kwargs)
