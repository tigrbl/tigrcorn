# Certification boundary

This document is the authoritative human-readable **in-bounds** statement for the current `tigrcorn` package boundary.

The canonical policy chain for the current package claim is:

- `docs/review/conformance/CERTIFICATION_BOUNDARY.md`
- `docs/review/conformance/certification_boundary.json`
- `docs/review/conformance/BOUNDARY_NON_GOALS.md`

This file defines what is **in bounds**. `certification_boundary.json` defines the per-RFC evidence policy. `BOUNDARY_NON_GOALS.md` defines what is explicitly **out of bounds**. Narrative documentation must not broaden, narrow, strengthen, or weaken the current package boundary outside those sources.

## Canonical boundary model

`tigrcorn` currently freezes its public package boundary as five categories:

- **T — transport**
  - package-owned TCP, Unix, UDP/QUIC, pipe, and in-process listener surfaces
  - package-owned TLS 1.3 server behavior on TCP/Unix listeners
  - QUIC transport, QUIC-TLS, recovery, retry, idle-timeout, and 0-RTT policy surfaces
  - ALPN, X.509 path validation, OCSP policy, and CRL policy integration that are part of the package-owned transport/security path
- **P — protocol**
  - HTTP/1.1, HTTP/2, HTTP/3, WebSocket, HPACK, and QPACK
  - CONNECT relay, trailer fields, content-coding negotiation, conditional requests, range requests, Early Hints, and the bounded Alt-Svc header-field advertisement profile
- **A — application hosting**
  - ASGI3 hosting, lifespan handling, package-defined lifecycle behavior, package-owned `StaticFilesApp`, and the programmatic/embedded serve path that belongs to the current package surface
- **D — delivery/origin behavior**
  - direct origin-style response behavior implemented by the package, including file-backed static delivery, conditional/range handling, HEAD behavior, response streaming/spooling, Early Hints emission, and bounded Alt-Svc advertisement
- **R — runtime/operator**
  - workers, reload, binding/listener configuration, proxy/header normalization, logging, metrics, concurrency/timeouts/resource controls, and the current supported runtime surface
  - the current supported public runtime surface is **`auto`, `asyncio`, and `uvloop`**
  - the reserved dependency extra `runtime-trio` does **not** widen the runtime contract or add a supported `trio` runtime claim

The current package claim is anchored to that T/P/A/D/R boundary. The boundary does **not** expand merely because peer servers expose broader pluggability, broader app-interface support, or broader product-layer features.

## Required RFC surface

The current required RFC surface remains:

- RFC 9112
- RFC 9113
- RFC 9114
- RFC 9000
- RFC 9001
- RFC 9002
- RFC 7541
- RFC 9204
- RFC 6455
- RFC 7692
- RFC 8441
- RFC 9220
- RFC 8446
- RFC 9110 §9.3.6 (CONNECT)
- RFC 9110 §6.5 (trailers)
- RFC 9110 §8 (content coding)
- RFC 7232
- RFC 7233
- RFC 8297
- RFC 7838 §3 (Alt-Svc header-field advertisement)
- RFC 5280
- RFC 6960
- RFC 7301

The machine-readable mapping of those RFCs to required evidence tiers remains `docs/review/conformance/certification_boundary.json`.

## Canonical evidence tiers

1. **local conformance** — `docs/review/conformance/corpus.json`
2. **same-stack replay** — `docs/review/conformance/external_matrix.same_stack_replay.json`
3. **independent certification** — `docs/review/conformance/external_matrix.release.json`

The current canonical release root is `docs/review/conformance/releases/0.3.9/release-0.3.9/`.

That root contains the canonical independent bundle, the canonical same-stack replay bundle, the canonical mixed compatibility bundle, the final flag/operator/performance certification bundles, and the preserved auxiliary bundles used during Phases 9B–9I.

Historical preserved roots remain in-tree for provenance:

- `docs/review/conformance/releases/0.3.2/release-0.3.2/`
- `docs/review/conformance/releases/0.3.6/release-0.3.6/`
- `docs/review/conformance/releases/0.3.6-current/release-0.3.6-current/`
- `docs/review/conformance/releases/0.3.6-rfc-hardening/release-0.3.6-rfc-hardening/`
- `docs/review/conformance/releases/0.3.7/release-0.3.7/`

The preserved `0.3.7` root remains the candidate next release root for the Phase 7 checkpoint only; it is not the current canonical release root.

The 0.3.9 canonical root is green under both the authoritative boundary and the stricter all-surfaces-independent target.

## Release-gate requirements

A release is not honestly certifiable until all of the following are true:

- every RFC named in the boundary has a declared evidence policy
- the declared evidence resolves through the current corpus / same-stack matrix / independent matrix
- the highest required evidence tier per RFC is satisfied
- every declared independent scenario has preserved passing artifacts in the canonical independent release bundle
- no scenario labelled `independent_certification` uses a same-stack peer
- package-owned TLS 1.3 evidence exists for the TCP/TLS listener path rather than delegating that path to `ssl.create_default_context`

## Current release note

The current release-gate result under this authoritative boundary is green, and the canonical 0.3.9 release root also remains green under the stricter target. The canonical `0.3.9` release root is also green under the preserved stricter target and under the composite promotion target, but those stricter profiles do **not** redefine the canonical package boundary.

The package-owned TCP/TLS condition is satisfied in this working tree.

The current machine-readable policy intentionally keeps the following RFC surfaces at `local_conformance` in the current release gate:

- RFC 7692
- RFC 9110 §9.3.6 (CONNECT)
- RFC 9110 §6.5 (trailers)
- RFC 9110 §8 (content coding)
- RFC 7232
- RFC 7233
- RFC 8297
- RFC 7838 §3 (Alt-Svc header-field advertisement)
- RFC 6960

Those RFCs are still part of the required surface. RFC 7232 / RFC 7233 remain package-owned direct-entity semantics, RFC 8297 is the current direct-delivery `103 Early Hints` target, and RFC 7838 is intentionally limited to the bounded `§3` Alt-Svc header-field advertisement profile.

## Phase 4 direct-delivery support envelope

The current authoritative boundary treats the following Phase 4 delivery surfaces as explicit RFC targets:

- **RFC 8297** — direct server support for `103 Early Hints`
- **RFC 7838 §3** — bounded Alt-Svc **header-field advertisement** support

Those targets are intentionally narrow and package-owned:

- RFC 8297 is certified only for direct server emission of `103` informational responses before the final response on HTTP/1.1, HTTP/2, and HTTP/3, with a safe informational-header policy that preserves `Link` fields and strips unsafe / connection-specific fields.
- RFC 7838 is certified only for the response-header-field advertisement surface implemented by `tigrcorn`: explicit `Alt-Svc` values and automatic `h3=":port"` advertisement derived from configured UDP HTTP/3 listeners on non-HTTP/3 responses.
- The current boundary does **not** claim HTTP/2 `ALTSVC` frame support, broader Alt-Svc cache-management semantics, or RFC 9218 prioritization.

## Relationship to stricter preserved targets and the development backlog

The preserved stricter profile remains documented in `docs/review/conformance/STRICT_PROFILE_TARGET.md` and `docs/review/conformance/certification_boundary.strict_target.json`.

That stricter profile is currently green, but it is a preserved stricter satisfied target for promotion/audit purposes rather than a competing public boundary.

The post-promotion **in-bounds** backlog now lives in `docs/review/conformance/NEXT_DEVELOPMENT_TARGETS.md`.

The authoritative **out-of-bounds** statement now lives in `docs/review/conformance/BOUNDARY_NON_GOALS.md`.
