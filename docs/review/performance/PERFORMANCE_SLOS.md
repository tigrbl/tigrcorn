This document now serves as fixed contract data for the stricter promotion-grade performance target while still preserving the historical note that the phase6 matrix is structurally useful but not yet sufficient.

# Performance SLO target

This performance target remains subordinate to `docs/review/conformance/STRICT_PROFILE_TARGET.md` for promotion readiness and does not itself strengthen any RFC claim.
This target document is `docs/review/performance/PERFORMANCE_SLOS.md`.

Performance closure is not an RFC claim. It is a release-quality product-performance target that must remain consistent with RFC-correctness-under-load.

## Current state

The performance section of `evaluate_promotion_target()` is now **green** in-repo.

The preserved performance roots still live under the historical `phase6_reference_baseline/` and `phase6_current_release/` paths, but those roots now carry the stricter Phase 9G metric, threshold, budget, and artifact contract.

The historical phase6 roots still matter because the phase6 matrix is structurally useful but not yet sufficient on its own without the stricter Phase 9G metric and threshold contract.

## What the strict target requires

The strict performance target now requires, at minimum:

- throughput
- p50, p95, p99, and p99.9 latency
- time to first byte
- handshake latency
- error rate
- scheduler rejections and protocol stalls
- CPU and RSS ceilings
- relative regression budgets for throughput, p99, p99.9, CPU, and RSS

## Lane separation

The preserved matrix now declares both required lanes:

1. **component regression**
   - low-noise same-stack regression profiles for narrow operational deltas

2. **end-to-end release**
   - release-lane profiles representing externally visible HTTP, WebSocket, CONNECT, trailer, content-coding, TLS / mTLS / OCSP, and observability surfaces

## Current blockers

The strict performance section is now green, but the overall promotion target is still blocked by non-performance work:

- preserved-but-non-passing HTTP/3 `aioquic` strict-target scenarios
- Phase 9H evaluator hardening
- Phase 9I release assembly

## Phase 9A contract freeze

Phase 9A froze the exact strict-performance contract in:

- `docs/review/conformance/PHASE9A_PROMOTION_CONTRACT_FREEZE.md`
- `docs/review/conformance/phase9a_promotion_contract.current.json`
- `docs/review/conformance/phase9a_execution_backlog.current.json`

## Phase 9G closure checkpoint

This checkpoint is documented through:

- `docs/review/conformance/PHASE9G_STRICT_PERFORMANCE_CLOSURE.md`
- `docs/review/conformance/phase9g_strict_performance.current.json`
- `docs/review/conformance/delivery/DELIVERY_NOTES_PHASE9G_STRICT_PERFORMANCE_CLOSURE.md`
