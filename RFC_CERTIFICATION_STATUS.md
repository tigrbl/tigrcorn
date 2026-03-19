# RFC certification status for the updated archive

This repository targets the package-wide certification boundary defined in `docs/review/conformance/CERTIFICATION_BOUNDARY.md`.

## Current authoritative status

Under that authoritative boundary, the package is now **certifiably fully RFC compliant**.

The canonical release gates pass against the committed tree, and the canonical independent bundle now includes preserved passing artifacts for every scenario required at the `independent_certification` tier. In other words, the independent-certification requirements in the authoritative boundary are satisfied.

## RFCs satisfied at `independent_certification`

- RFC 9112
- RFC 9113
- RFC 9114
- RFC 9000
- RFC 9001
- RFC 9002
- RFC 7541
- RFC 9204
- RFC 6455
- RFC 8441
- RFC 9220
- RFC 8446
- RFC 5280
- RFC 7301

## RFCs intentionally satisfied at `local_conformance`

The authoritative boundary intentionally keeps these RFC surfaces at `local_conformance` in the current release gate:

- RFC 7692
- RFC 9110 §9.3.6
- RFC 9110 §6.5
- RFC 9110 §8
- RFC 6960

Those surfaces remain part of the required RFC surface, and the package satisfies them at the tier required by the authoritative machine-readable boundary.

## What changed in this checkpoint

This checkpoint closes the previously missing independent HTTP/3 / QUIC / RFC 9220 evidence by committing preserved passing third-party `aioquic` artifacts for:

- HTTP/3 request/response
- mTLS
- Retry
- resumption
- 0-RTT
- migration
- GOAWAY / QPACK observation
- RFC 9220 WebSocket-over-HTTP/3

The runtime and adapter work needed to make those artifacts honest is now committed in-tree.

## Current follow-on work outside the authoritative boundary

The repository still preserves broader, non-authoritative follow-on work:

- a stricter all-surfaces-independent overlay for RFC 7692, RFC 9110 CONNECT / trailers / content coding, and RFC 6960
- a provisional QUIC / HTTP/3 flow-control review bundle
- a seed intermediary / proxy corpus

Those items are future-strengthening work. They do not change the current passing release-gate result.

## Validation performed for this checkpoint

- `PYTHONPATH=src:. python -c "from tigrcorn.compat.release_gates import evaluate_release_gates; report = evaluate_release_gates('.'); print(report.passed, len(report.failures))"`
- result: `True 0`

The machine-readable release-gate status for this checkpoint lives in `docs/review/conformance/release_gate_status.current.json`.
