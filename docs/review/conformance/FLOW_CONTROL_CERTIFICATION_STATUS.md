
# Flow-control certification status

The authoritative package-wide certification target remains `docs/review/conformance/CERTIFICATION_BOUNDARY.md`.

This status file tracks the repository-level QUIC / HTTP/3 flow-control evidence roots that sit outside the current primary canonical release-gate blockers.

## What this update adds

- a new tooling entrypoint: `tools/create_minimum_certified_flow_control_bundle.py`
- a new independent evidence root: `docs/review/conformance/releases/0.3.6/release-0.3.6/tigrcorn-minimum-certified-flow-control-matrix/`
- a new reference matrix: `docs/review/conformance/external_matrix.flow_control.minimum.json`
- retention of the earlier provisional review bundle for historical provenance

## What the new bundle is

The minimum certified flow-control bundle is promoted from already-preserved third-party `aioquic` HTTP/3 artifacts.
It preserves a stable release-gate-eligible evidence root for:

- credit exhaustion
- replenishment
- stream-level backpressure
- connection-level backpressure
- QPACK blocked-stream behavior
- GOAWAY / pressure behavior

Each scenario directory is marked with:

- `release_gate_eligible: true`
- `source_independent_scenario`
- `flow_control_certified_scope`
- `flow_control_metadata.json`
- links back to the local vectors used to keep the bundle traceable to the conformance corpus

## Current honest status

Broad ecosystem QUIC / HTTP/3 flow-control certification is still not finished, but the repository no longer depends only on the provisional same-stack review bundle.

The new minimum certified flow-control root is a real independent evidence bundle promoted from preserved third-party `aioquic` artifacts.
The older provisional flow-control bundle remains in-tree as a historical / planning aid and is still explicitly non-certifying.

## Closure procedure

1. Keep the now-preserved minimum independent flow-control bundle in the canonical release root.
2. Continue adding broader third-party QUIC / HTTP/3 flow-control artifacts that separately exercise additional peer stacks and richer backpressure cases.
3. Keep the provisional same-stack review bundle only as a provenance aid until the broader ecosystem matrix is preserved.
