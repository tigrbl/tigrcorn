from __future__ import annotations

import pytest

from tigrcorn.contract import security_metadata
from tigrcorn.errors import ProtocolError
from tests.contract_closure_assertions import ContractClosureAssertions


class ContractSNIMetadataTests(ContractClosureAssertions):
    def test_sni_metadata_contract(self) -> None:
        self.assert_security_metadata('sni')


def test_sni_metadata_preserves_hostname() -> None:
    assert security_metadata(tls=True, sni="api.example.test").as_dict() == {
        "tls": True,
        "sni": "api.example.test",
    }


@pytest.mark.parametrize("sni", ["", "   ", ".example.test", "example..test", "example.test."])
def test_sni_metadata_fails_closed_for_lossy_or_malformed_hostnames(sni: str) -> None:
    with pytest.raises(ProtocolError):
        security_metadata(tls=True, sni=sni)
