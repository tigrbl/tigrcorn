# Delivery notes — RFC applicability and competitor support update

This checkpoint adds a focused standards-applicability and competitor-support audit for the RFC table covering:

- RFC 7232
- RFC 9110
- RFC 9111
- RFC 9530
- RFC 7515
- RFC 7516
- RFC 7519
- RFC 8152
- RFC 9052
- RFC 9421

It also records a current competitor matrix for:

- Uvicorn
- Hypercorn
- Daphne
- Granian

## Files added

- `docs/review/conformance/RFC_APPLICABILITY_AND_COMPETITOR_STATUS.md`
- `docs/review/conformance/rfc_applicability_and_competitor_status.current.json`
- `tests/test_rfc_applicability_and_competitor_status.py`

## Files updated

- `README.md`
- `docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md`
- `docs/review/conformance/README.md`

## Honest result

- The RFCs from the user-supplied table that are **currently core-applicable** to `tigrcorn` are RFC 9112, RFC 9113, RFC 9114, and bounded RFC 9110 sections for CONNECT, trailer fields, and content coding.
- The best **next RFC-rooted additions** are RFC 7232 and RFC 9530.
- RFC 9111 and RFC 9421 should remain **conditional** until the product boundary expands into cache or gateway roles.
- JOSE / COSE RFCs remain **outside the core transport-server boundary**.
- Competitor review material is recorded with an explicit evidence-policy note so “no official support claim found” is not overread as a proof of impossibility.

## Validation run for this update

```bash
PYTHONPATH=src:. pytest -q   tests/test_rfc_applicability_and_competitor_status.py   tests/test_http_integrity_caching_signatures_status.py   tests/test_release_gates.py   tests/test_phase8_promotion_targets.py
```

The authoritative release-gate boundary remains green after this documentation and test update. The stricter promotion target remains red for the previously documented reasons.
