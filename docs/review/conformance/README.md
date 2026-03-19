# Conformance and external interoperability evidence

The canonical package-wide certification target is defined in `docs/review/conformance/CERTIFICATION_BOUNDARY.md`.

## Current canonical release root

The current release evidence is consolidated under `docs/review/conformance/releases/0.3.6/release-0.3.6/`.

That root contains three normative bundles for the current package version plus preserved historical / planning bundles:

- `tigrcorn-independent-certification-release-matrix/`
- `tigrcorn-same-stack-replay-matrix/`
- `tigrcorn-mixed-compatibility-release-matrix/`
- `tigrcorn-provisional-http3-gap-bundle/` (preserved historical non-certifying review bundle)
- `tigrcorn-provisional-all-surfaces-gap-bundle/` (preserved non-certifying stricter-profile planning bundle)
- `tigrcorn-provisional-flow-control-gap-bundle/` (preserved non-certifying QUIC / HTTP/3 flow-control review bundle)

The older `0.3.2`, `0.3.6-rfc-hardening`, and `0.3.6-current` directories remain preserved for provenance, but they are not the canonical current release root.

## 1. Local conformance corpus

`corpus.json` maps RFC-oriented behavior to local fixtures and unit tests.

## 2. Same-stack replay evidence

`external_matrix.same_stack_replay.json` isolates replayable scenarios that still use tigrcorn-owned peers such as `tigrcorn-public-client`.

Those scenarios are useful regression evidence. They are not independent certification evidence.

## 3. Independent certification evidence

`external_matrix.release.json` is the canonical independent certification matrix.

That matrix now includes preserved passing artifacts for:

- HTTP/1.1
- HTTP/2
- HTTP/2 over TLS
- WebSocket over HTTP/1.1
- RFC 8441 WebSocket over HTTP/2
- OpenSSL QUIC handshake interoperability
- third-party `aioquic` HTTP/3 request/response and QUIC feature-axis scenarios
- third-party `aioquic` RFC 9220 WebSocket-over-HTTP/3 scenarios

## Current authoritative status

The package is now **certifiably fully RFC compliant under the authoritative certification boundary**.

The remaining broader items are explicitly outside that authoritative blocker set:

- RFC 7692, RFC 9110 CONNECT / trailers / content coding, and RFC 6960 remain intentionally bounded at `local_conformance` in the current machine-readable policy
- a stricter all-surfaces-independent overlay still exists for those surfaces and remains incomplete
- the provisional all-surfaces and flow-control bundles remain non-certifying review aids
- the intermediary / proxy seed corpus improves repository completeness but is not itself a certification bundle

For the explicit policy decision that resolved the earlier documentation mismatch, see `docs/review/conformance/CERTIFICATION_POLICY_ALIGNMENT.md`.

For historical offline remediation artifacts and strict-profile planning material, see `docs/review/conformance/OFFLINE_COMPLETION_ATTEMPT.md`, `docs/review/conformance/offline_completion_state.json`, `docs/review/conformance/ALL_SURFACES_INDEPENDENT_STATUS.md`, `docs/review/conformance/all_surfaces_independent_state.json`, `docs/review/conformance/FLOW_CONTROL_CERTIFICATION_STATUS.md`, `docs/review/conformance/SECONDARY_PARTIALS_STATUS.md`, and `docs/review/conformance/secondary_partials_state.json`.
