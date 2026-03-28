# Boundary non-goals

This document is the authoritative human-readable **out-of-bounds** statement for the current `tigrcorn` package boundary.

The canonical policy chain for the current package claim is:

- `docs/review/conformance/CERTIFICATION_BOUNDARY.md`
- `docs/review/conformance/certification_boundary.json`
- `docs/review/conformance/BOUNDARY_NON_GOALS.md`

If future work chooses to adopt any currently excluded surface, the package boundary and the current-state chain must be updated first. Peer feature comparisons, roadmap notes, or reserved dependency extras do **not** widen the current public package boundary by themselves.

## 1. RFC and feature-family non-goals

The following standards/features are explicitly outside the current package boundary:

- **Trio runtime** as a supported public runtime family
- **RFC 9218** prioritization
- **RFC 9111** caching / freshness policy
- **RFC 9530** digest fields
- **RFC 9421** HTTP signatures / message signatures
- **JOSE** / **COSE** stacks and adjacent token/signature-envelope product layers

These surfaces may be revisited only through an explicit future boundary change. They are not part of the current certification target and they are not part of the current in-bounds backlog.

## 2. Implementation-pluggability non-goals

The current package boundary does **not** include public pluggability for:

- HTTP parser/backend selection
- WebSocket backend/engine selection
- alternate app-interface serving such as ASGI2, WSGI, or RSGI selection
- broad custom loop-factory selection
- runtime thread-topology/task-engine abstraction families

`tigrcorn` is currently a package-owned transport/runtime server with a package-defined ASGI3 hosting surface. Peer servers exposing those broader pluggability families does not create a current `tigrcorn` obligation.

## 3. Runtime and dependency-governance non-goals

The current supported public runtime surface is:

- `auto`
- `asyncio`
- `uvloop`

The declared optional extra `runtime-trio` is a **reserved dependency path only**. It does not advertise or imply support for `--runtime trio`.

## 4. Transport-policy non-goals

The current package posture also keeps the following outside the public surface unless the boundary is explicitly widened:

- TLS minimum-version downgrade controls below the current package-owned TLS posture
- broader Alt-Svc caching/frame semantics beyond the bounded RFC 7838 §3 header-field advertisement surface
- broader caching/integrity/signature gateway behavior that would move `tigrcorn` beyond its current direct transport/runtime/origin-style boundary

## 5. Governance rules

The current package boundary must be interpreted with these rules:

- `CERTIFICATION_BOUNDARY.md` defines what is in bounds.
- `BOUNDARY_NON_GOALS.md` defines what is out of bounds.
- `NEXT_DEVELOPMENT_TARGETS.md` can only track work that stays inside the in-bounds boundary and outside the explicit non-goals.
- historical strict-target or phase-planning documents do not override the current in-bounds / out-of-bounds policy chain.
- reserved extras, peer deltas, and speculative roadmap notes do not create public support obligations.

## 6. Current-state note

Under the current canonical `0.3.9` boundary and release root, the package remains certifiably fully RFC compliant and certifiably fully featured.

This out-of-bounds document exists to keep that claim honest while the repository continues post-promotion in-bounds work from `tigrcorn_unified_policy_matrix.md`.
