# Flow-control certification status

The authoritative package-wide certification target remains `docs/review/conformance/CERTIFICATION_BOUNDARY.md`.

This status file tracks the repository-level QUIC / HTTP/3 flow-control review material that sits outside the current primary release-gate blockers.

## What this update adds

- a new offline tooling entrypoint: `tools/create_provisional_flow_control_gap_bundle.py`
- a new review bundle: `docs/review/conformance/releases/0.3.6/release-0.3.6/tigrcorn-provisional-flow-control-gap-bundle/`
- explicit links from same-stack HTTP/3 replay artifacts to the local QUIC / HTTP/3 flow-control vectors in `corpus.json`

## What the new bundle is

The provisional flow-control gap bundle is generated from the same-stack HTTP/3 replay matrix.
It preserves a stable review root for:

- basic HTTP/3 request-stream credit behavior
- Retry-associated QUIC / HTTP/3 flow behavior
- 0-RTT-associated flow behavior
- migration-associated flow behavior
- GOAWAY / QPACK backpressure behavior

Each scenario directory is marked with:

- `provisional_non_certifying_substitution: true`
- `release_gate_eligible: false`
- `flow_control_review_only: true`
- `source_same_stack_scenario`
- `linked_local_vectors`

## Current honest status

Broad independent QUIC / HTTP/3 flow-control certification is still incomplete.
The new review bundle improves repository transparency and gives the gap a formal artifact root, but it does not satisfy `required_rfc_evidence` for any stricter flow-control-specific overlay and does not change the current green canonical release-gate outcome.

## Closure procedure

1. Keep the now-complete canonical HTTP/3 / RFC 9220 closure work from `docs/review/conformance/INDEPENDENT_HTTP3_CERTIFICATION_STATE.md`.
2. Preserve third-party QUIC / HTTP/3 flow-control artifacts that specifically exercise credit exhaustion, replenishment, and backpressure behavior.
3. Replace the provisional same-stack review bundle with real independent artifacts once those runs are preserved.
