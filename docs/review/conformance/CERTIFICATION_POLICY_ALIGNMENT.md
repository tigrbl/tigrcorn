# Certification policy alignment

The canonical policy source for package-wide certification is `docs/review/conformance/CERTIFICATION_BOUNDARY.md` together with `docs/review/conformance/certification_boundary.json`.

## Decision made in this update

The machine-readable boundary is authoritative.

That means the current release gate uses the per-RFC evidence tier declared in `required_rfc_evidence`, and narrative documentation must not silently strengthen that requirement into an all-surfaces-independent rule.

## RFC surfaces affected by the earlier mismatch

The current boundary intentionally keeps these RFCs at `local_conformance`:

- RFC 7692
- RFC 9110 §9.3.6 (CONNECT)
- RFC 9110 §6.5 (trailers)
- RFC 9110 §8 (content coding)
- RFC 6960

Those RFCs are still inside the required package surface. They are simply not required to reach `independent_certification` in the current release gate.

## Why this choice was made

- the repository already contains local conformance evidence for those RFCs
- the immediate certification blocker is preserved third-party HTTP/3 / RFC 9220 evidence, not a missing local implementation
- promoting the listed RFCs to `independent_certification` without preserved third-party artifacts would make the boundary stricter than the evidence actually committed in the tree

## What would be required for a stricter profile

A stricter all-surfaces-independent profile would still need new third-party preserved artifacts for:

- RFC 7692 permessage-deflate behavior
- RFC 9110 CONNECT relay behavior
- RFC 9110 trailer propagation
- RFC 9110 content-coding negotiation
- RFC 6960 OCSP-backed revocation behavior

## Current repository state

This update resolves the policy/documentation mismatch, but it does **not** make the archive certifiably fully RFC compliant.

The current release remains blocked by the missing preserved third-party `aioquic` HTTP/3 / RFC 9220 artifacts declared in `docs/review/conformance/external_matrix.release.json`.
