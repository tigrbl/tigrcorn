# Release gate status

The canonical package-wide certification target is defined in `docs/review/conformance/CERTIFICATION_BOUNDARY.md`.

## Current result

- `evaluate_release_gates('.')` → `passed=True`
- `failure_count=0`

The canonical release gates are now green.

Under the authoritative certification boundary, the package is **certifiably fully RFC compliant**.

## What changed relative to the earlier gap state

The canonical independent release bundle now contains preserved passing third-party `aioquic` artifacts for the previously missing HTTP/3 / QUIC feature-axis / RFC 9220 scenarios, and those scenarios are enabled in `docs/review/conformance/external_matrix.release.json`.

That closes the independent-certification requirements for:

- RFC 9114
- RFC 9000
- RFC 9001
- RFC 9002
- RFC 9204
- RFC 9220

## Non-blocking follow-on work

The repository still preserves broader, non-authoritative follow-on work:

- a stricter all-surfaces-independent overlay for RFC 7692, RFC 9110 CONNECT / trailers / content coding, and RFC 6960
- a provisional QUIC / HTTP/3 flow-control review bundle
- a seed intermediary / proxy corpus

Those items do not change the current passing release-gate result.

A machine-readable copy of this status is stored in `docs/review/conformance/release_gate_status.current.json`.
