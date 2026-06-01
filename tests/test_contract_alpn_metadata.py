from __future__ import annotations

import pytest

from tigrcorn.contract import security_metadata
from tigrcorn.errors import ProtocolError
from tests.contract_closure_assertions import ContractClosureAssertions


class ContractALPNMetadataTests(ContractClosureAssertions):
    def test_alpn_metadata_contract(self) -> None:
        self.assert_security_metadata('alpn')


@pytest.mark.parametrize("alpn", ["http/1.1", "h2", "h3"])
def test_alpn_metadata_accepts_governed_protocol_tokens(alpn: str) -> None:
    assert security_metadata(tls=True, alpn=alpn).as_dict() == {"tls": True, "alpn": alpn}


@pytest.mark.parametrize("alpn", ["", "   ", "h4", "spdy/3", "HTTP/1.1"])
def test_alpn_metadata_fails_closed_for_unknown_or_lossy_tokens(alpn: str) -> None:
    with pytest.raises(ProtocolError):
        security_metadata(tls=True, alpn=alpn)
