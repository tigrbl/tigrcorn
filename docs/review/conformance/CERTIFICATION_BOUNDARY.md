# Certification boundary

This canonical boundary document is `docs/review/conformance/CERTIFICATION_BOUNDARY.md`.

`tigrcorn` targets **package-wide RFC coverage across all advertised surfaces, with the required evidence tier declared per RFC in this boundary**.

This boundary is authoritative for certification policy. Narrative docs must not strengthen or weaken the required evidence tier outside this file and `docs/review/conformance/certification_boundary.json`.

## Canonical evidence tiers

1. **local conformance** — `docs/review/conformance/corpus.json`
2. **same-stack replay** — `docs/review/conformance/external_matrix.same_stack_replay.json`
3. **independent certification** — `docs/review/conformance/external_matrix.release.json`

The current canonical release root is `docs/review/conformance/releases/0.3.8/release-0.3.8/`.

That root contains the canonical independent bundle, the canonical same-stack replay bundle, the canonical mixed compatibility bundle, the final flag/operator/performance certification bundles, and the preserved auxiliary bundles used during Phases 9B–9I.

Historical preserved roots remain in-tree for provenance:

- `docs/review/conformance/releases/0.3.2/release-0.3.2/`
- `docs/review/conformance/releases/0.3.6/release-0.3.6/`
- `docs/review/conformance/releases/0.3.6-current/release-0.3.6-current/`
- `docs/review/conformance/releases/0.3.6-rfc-hardening/release-0.3.6-rfc-hardening/`
- `docs/review/conformance/releases/0.3.7/release-0.3.7/`

The 0.3.8 canonical root is green under both the authoritative boundary and the stricter all-surfaces-independent target.

## Required RFC surface

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
- RFC 5280
- RFC 6960
- RFC 7301

The machine-readable mapping of those RFCs to required evidence lives in `docs/review/conformance/certification_boundary.json`.

## Release-gate requirements

A release is not honestly certifiable until all of the following are true:

- every RFC named in the boundary has a declared evidence policy
- the declared evidence resolves through the current corpus / same-stack matrix / independent matrix
- the highest required evidence tier per RFC is satisfied
- every declared independent scenario has preserved passing artifacts in the canonical independent release bundle
- no scenario labelled `independent_certification` uses a same-stack peer
- package-owned TLS 1.3 evidence exists for the TCP/TLS listener path rather than delegating that path to `ssl.create_default_context`

## Current repository note

The package-owned TCP/TLS condition is satisfied in this working tree.

The current machine-readable policy intentionally keeps the following RFC surfaces at `local_conformance` in the current release gate:

- RFC 7692
- RFC 9110 §9.3.6 (CONNECT)
- RFC 9110 §6.5 (trailers)
- RFC 9110 §8 (content coding)
- RFC 6960

Those RFCs are still part of the required surface. They are not independent-certification blockers under the current authoritative boundary. A stricter all-surfaces-independent profile would require additional third-party preserved artifacts for them.

The previously missing third-party HTTP/3 / RFC 9220 artifacts have now been regenerated and promoted for the declared `aioquic` adapter scenarios.

The current release-gate result under this authoritative boundary is green, and the canonical 0.3.8 release root also remains green under the stricter target.

This file is the single source of truth that the README, protocol docs, conformance docs, hardening report, RFC review, RFC certification status, and current-state summary reference.


## Dual-boundary note

The current public claim remains anchored to this authoritative boundary.

A stricter target is documented separately in `docs/review/conformance/STRICT_PROFILE_TARGET.md` and `docs/review/conformance/certification_boundary.strict_target.json`.

That stricter target is now green and is satisfied by the canonical 0.3.8 release root, but the authoritative certification policy remains declared in this boundary file.
