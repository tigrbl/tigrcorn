import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOUNDARY_DOC = "docs/review/conformance/CERTIFICATION_BOUNDARY.md"
BOUNDARY_JSON = "docs/review/conformance/certification_boundary.json"
POLICY_DOC = "docs/review/conformance/CERTIFICATION_POLICY_ALIGNMENT.md"


def test_boundary_claim_is_per_rfc_and_authoritative() -> None:
    payload = json.loads((ROOT / BOUNDARY_JSON).read_text(encoding="utf-8"))
    claim = payload["claim"]
    assert "required evidence tier declared per RFC" in claim


def test_policy_docs_name_local_tier_rfcs_explicitly() -> None:
    text = (ROOT / POLICY_DOC).read_text(encoding="utf-8")
    assert BOUNDARY_DOC in text
    for needle in (
        "RFC 7692",
        "RFC 9110 §9.3.6",
        "RFC 9110 §6.5",
        "RFC 9110 §8",
        "RFC 7232",
        "RFC 7233",
        "RFC 8297",
        "RFC 7838 §3",
        "RFC 6960",
    ):
        assert needle in text
    assert "certifiably fully RFC compliant" in text
