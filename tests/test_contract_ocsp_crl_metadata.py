from __future__ import annotations

import pytest

from tigrcorn.contract import security_metadata
from tigrcorn.errors import ProtocolError
from tests.contract_closure_assertions import ContractClosureAssertions


class ContractOCSPCRLMetadataTests(ContractClosureAssertions):
    def test_ocsp_crl_metadata_contract(self) -> None:
        self.assert_security_metadata('ocsp')


@pytest.mark.parametrize("ocsp_status", ["good", "revoked", "unknown", "unavailable", "not_provided"])
def test_ocsp_metadata_accepts_governed_statuses(ocsp_status: str) -> None:
    assert security_metadata(tls=True, ocsp_status=ocsp_status).as_dict() == {
        "tls": True,
        "ocsp_status": ocsp_status,
    }


@pytest.mark.parametrize("crl_status", ["checked", "clear", "revoked", "unknown", "unavailable", "not_provided"])
def test_crl_metadata_accepts_governed_statuses(crl_status: str) -> None:
    assert security_metadata(tls=True, crl_status=crl_status).as_dict() == {
        "tls": True,
        "crl_status": crl_status,
    }


@pytest.mark.parametrize(
    "kwargs",
    [
        {"tls": True, "ocsp_status": ""},
        {"tls": True, "ocsp_status": "stapled"},
        {"tls": True, "crl_status": "   "},
        {"tls": True, "crl_status": "fresh"},
    ],
)
def test_ocsp_crl_metadata_fails_closed_for_lossy_or_unknown_statuses(kwargs: dict[str, object]) -> None:
    with pytest.raises(ProtocolError):
        security_metadata(**kwargs)
