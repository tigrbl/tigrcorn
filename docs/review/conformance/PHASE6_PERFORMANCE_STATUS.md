# Phase 6 performance status

This repository still preserves the historical **Phase 6** performance roots, but those preserved roots now carry the richer **Phase 9G** artifact and metric contract.

## What remains true from Phase 6

- `src/tigrcorn/compat/perf_runner.py` exists and remains the performance harness entry point
- `tools/run_perf_matrix.py` remains the CLI entry point for running and validating the matrix
- `benchmarks/` still provides the required performance-driver catalog
- the preserved baseline and current-release roots still live under:
  - `docs/review/performance/artifacts/phase6_reference_baseline/`
  - `docs/review/performance/artifacts/phase6_current_release/`

## What changed by Phase 9G

The preserved performance roots now also carry:

- p99.9 latency
- time-to-first-byte metrics
- handshake latency metrics
- protocol-stall totals
- richer threshold keys
- richer relative regression budgets
- explicit lane metadata
- certification-platform metadata
- per-profile `summary.json`

## Honest result

- the authoritative RFC boundary remains green
- performance closure remains a **separate product-performance claim surface**
- the performance section of `evaluate_promotion_target()` is now green
- the overall promotion target remains non-green because preserved HTTP/3 `aioquic` strict-target evidence is still not marked passing

## Qualification

This remains a package-local performance certification surface. It is suitable for reproducible release gating inside the repository. It is **not** an independent third-party performance certification program.
