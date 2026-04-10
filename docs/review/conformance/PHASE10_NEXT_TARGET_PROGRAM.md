# Phase 10 Next-Target Program

This document freezes the **post-0.3.9 next-target execution program** for the mutable working tree.

It does not widen the current package boundary by itself. The governing policy remains:

- `docs/review/conformance/CERTIFICATION_BOUNDARY.md`
- `docs/review/conformance/certification_boundary.json`
- `docs/review/conformance/BOUNDARY_NON_GOALS.md`

## Program objective

The next-target program for the current repository line is:

1. implement the documented Wave 1 and Wave 2 **in-bounds** candidate work
2. keep the current authoritative boundary green while doing so
3. convert promoted candidate rows into package-owned implemented and certified claims
4. make repository governance cleanliness and remote automation verification part of release discipline
5. close the remote GitHub/TestPyPI/PyPI control-plane gap honestly rather than treating local workflow files as sufficient proof

This program is intentionally narrower than a boundary expansion. RFC 9218, RFC 9111, RFC 9530, RFC 9421, JOSE/COSE, Trio runtime support, parser/backend pluggability, WebSocket engine pluggability, and alternate app-interface families remain out of scope unless the boundary docs change first.

## Required work bands

### Phase 0

- freeze this next-target contract and machine-readable checkpoint
- reconcile mutable issue/risk notes with the canonical current-state chain
- treat already-landed fixes as historical or administrative close-out items, not active package defects
- make path/name governance policy explicit through grandfathered exemptions plus CI enforcement
- keep release-line semantics at patch level unless a later change intentionally widens the public boundary

### Phase 1

- deliver the current Wave 1 in-bounds hardening program:
  - deployment profiles
  - base and profile-effective default audits
  - reviewed flag contract truth
  - proxy/public-policy closure
  - TLS/X.509 peer-certification closure
  - QUIC early-data/replay/topology semantics
  - origin/static/pathsend contract closure

### Phase 2

- deliver the current Wave 2 in-bounds evidence and governance program:
  - RFC 9651 structured-fields baseline
  - package-owned field-behavior inventory and termination posture
  - observability/export contract closure
  - negative-certification bundles
  - machine-linked claims/risks/tests/evidence discipline
  - retained evidence/performance/governance inputs as required release-gate inputs

### Phase 3

- ensure repo-side automation and remote activation both exist and are verified:
  - GitHub required checks and rulesets
  - protected environments
  - Pages deployment
  - TestPyPI and PyPI trusted publishing
  - release asset attachment
  - artifact attestations
  - CodeQL and Dependabot policy activation

### Phase 4

- create a new versioned release root
- regenerate manifests, indexes, summaries, release notes, and current-state chain artifacts
- update version metadata and canonical pointers
- freeze the new root

## Governance-cleanliness rule

`python tools/govchk.py scan` is now part of the mutable-tree validation contract.

The current tree uses explicit grandfathered exemptions for legacy mutable support files whose names exceed the post-migration limits, including:

- `LEGACY_UNITTEST_INVENTORY.json`
- `docs/reference/risk_register.schema.json`
- `assets/tigrcorn_brand_frag_light.png`
- `assets/tigrcorn_brand_frag_dark.png`

Those exemptions preserve current paths without treating them as a license for new violations.

## Remote honesty rule

Repository-local workflow files are necessary but not sufficient for a full automation claim.

The next-target program is complete only when the external systems themselves show:

- active branch/tag protections and required checks
- active protected environments
- successful Pages deployment
- successful trusted-publisher registration and package publication
- successful release asset attachment
- successful artifact attestations

Until then, the repository may claim **automation scaffolding exists locally**, but it must not claim **remote automation is fully active and verified**.
