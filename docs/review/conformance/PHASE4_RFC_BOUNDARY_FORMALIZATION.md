# Phase 4 RFC boundary formalization

This document records the explicit **Step 7** certification-boundary decision for the current package boundary.

## Certified Phase 4 RFC targets

The current authoritative boundary and the strict target now include:

- `RFC 8297`
- `RFC 7838 §3`

Both are currently declared at the `local_conformance` evidence tier.

## Exact support envelope

### RFC 8297

The certified package surface is the direct-server `103 Early Hints` behavior already implemented across:

- HTTP/1.1
- HTTP/2
- HTTP/3

The support envelope is intentionally narrow and safe:

- only `103 Early Hints` is targeted
- informational headers are sanitized through the current `tigrcorn.http.early_hints` policy
- the supported public behavior is the current direct-delivery server feature, not a broader intermediary/gateway product surface

The declared local conformance vector is:

- `http-early-hints`

### RFC 7838 §3

The certified package surface is the bounded **Alt-Svc response header-field advertisement** profile.

The support envelope is intentionally bounded:

- explicit and automatic `Alt-Svc` response header-field emission is targeted
- the package currently certifies only the **header-field advertisement** profile under `RFC 7838 §3`
- broader protocol-level Alt-Svc framing and any wider advertisement/cache model are not claimed in the current package boundary

The declared local conformance vector is:

- `http-alt-svc-header-advertisement`

## Explicit non-target

The current package boundary does **not** certify `RFC 9218`.

Prioritization remains outside the current authoritative / strict package boundary unless and until tigrcorn adopts an explicit prioritization feature surface and associated evidence model.

## Boundary effect

After this checkpoint:

- Early Hints is no longer an ambiguous implemented-only feature surface; it is an explicit current-boundary RFC target
- Alt-Svc is no longer an ambiguous implemented-only feature surface; it is an explicit current-boundary **bounded** RFC target
- `RFC 9218` remains explicitly out of scope
- this checkpoint does **not** widen the package boundary into caching/freshness, digest/signature trust, JOSE, COSE, or gateway enforcement
