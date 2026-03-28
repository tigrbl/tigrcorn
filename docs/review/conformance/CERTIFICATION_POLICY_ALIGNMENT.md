# Certification policy alignment

The canonical policy source for package-wide certification is now the explicit policy chain:

- `docs/review/conformance/CERTIFICATION_BOUNDARY.md`
- `docs/review/conformance/certification_boundary.json`
- `docs/review/conformance/BOUNDARY_NON_GOALS.md`

## Decision preserved in this update

The machine-readable boundary remains authoritative for per-RFC evidence policy.

The human-readable boundary document is authoritative for the current in-bounds T/P/A/D/R package statement.

The boundary non-goals document is authoritative for the current out-of-bounds statement.

That means the current release gate uses the per-RFC evidence tier declared in `required_rfc_evidence`, while current docs also have one explicit place that says what the package is **not** claiming.

## RFC surfaces intentionally satisfied at local conformance in the canonical boundary

The current boundary intentionally keeps these RFCs at `local_conformance`:

- RFC 7692
- RFC 9110 §9.3.6 (CONNECT)
- RFC 9110 §6.5 (trailers)
- RFC 9110 §8 (content coding)
- RFC 7232
- RFC 7233
- RFC 8297
- RFC 7838 §3
- RFC 6960

Those RFCs are still inside the required package surface. RFC 7232 / RFC 7233 are current package-owned entity semantics, RFC 8297 is the current 103 Early Hints direct-delivery surface, and RFC 7838 §3 is the current bounded Alt-Svc header-field advertisement surface.

## Current repository state

The current canonical `0.3.9` release root is green under:

- the canonical certification boundary
- the preserved stricter target
- the composite promotion target

The package is therefore currently **certifiably fully RFC compliant** under the canonical boundary and **certifiably fully featured** under the canonical `0.3.9` release root.

## Current governance note

The new out-of-bounds statement in `BOUNDARY_NON_GOALS.md` resolves repeated review ambiguity around Trio/runtime breadth, RFC 9218, RFC 9111, RFC 9530, RFC 9421, JOSE/COSE, and parser/backend/interface pluggability.
