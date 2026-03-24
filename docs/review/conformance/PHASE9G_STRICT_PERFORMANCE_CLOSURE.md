# Phase 9G strict performance target closure

This checkpoint executes **Phase 9G** of the Phase 9 implementation plan.

It upgrades the preserved performance harness from the earlier phase6 threshold subset into the stricter promotion-grade contract that the current composite promotion evaluator expects.

## What changed

### 1. The preserved performance matrix now carries explicit lane separation

`docs/review/performance/performance_matrix.json` now classifies every required profile into one of two required lanes:

- `component_regression`
- `end_to_end_release`

The matrix also records certification-platform identifiers and per-profile lane metadata.

### 2. The preserved artifacts now expose the stricter metric keys

Every preserved current-release and baseline profile artifact now carries the additional strict-target metrics:

- `p99_9_ms`
- `time_to_first_byte_ms`
- `handshake_latency_ms`
- `protocol_stalls`

Those metrics are now emitted by `src/tigrcorn/compat/perf_runner.py` and preserved into the current artifact roots.

### 3. The matrix now declares the stricter threshold and regression-budget keys

Every profile in the matrix now declares the additional absolute-threshold keys:

- `max_p50_ms`
- `max_p95_ms`
- `max_p99_9_ms`
- `max_time_to_first_byte_ms`
- `max_handshake_latency_ms`
- `max_protocol_stalls`
- `max_rss_kib`
- `max_scheduler_rejections`

Every profile now also declares the additional relative-regression keys:

- `max_p99_9_increase_fraction`
- `max_cpu_increase_fraction`
- `max_rss_increase_fraction`

### 4. Profile artifacts are now richer and self-describing

Every profile artifact directory now preserves:

- `result.json`
- `summary.json`
- `env.json`
- `percentile_histogram.json`
- `raw_samples.csv`
- `command.json`
- `correctness.json`

The profile artifacts now include lane and certification-platform metadata alongside the threshold and regression evaluation payloads.

### 5. The performance section of `evaluate_promotion_target()` is now green

After this checkpoint:

- the performance section of `evaluate_promotion_target()` passes
- the authoritative boundary remains green
- the overall promotion target remains non-green only because the preserved HTTP/3 `aioquic` strict-target scenarios are still not marked passing

## Honest current result

This checkpoint closes only **Phase 9G**.

What is true now:

- the authoritative boundary remains green
- the strict target remains non-green because three preserved HTTP/3 `aioquic` scenarios are still not marked passing
- the flag surface remains green
- the operator surface remains green
- the performance section is now **green**
- the composite promotion target remains non-green

So this repository is still **not yet certifiably fully featured** under the stricter promotion target, and it is still **not yet strict-target certifiably fully RFC compliant**.

## Important scope note

This checkpoint closes the **promotion-gate-visible** strict performance contract currently enforced by `evaluate_promotion_target()`.

Phase **9H** still remains in the execution plan because it hardens the evaluator so the full declared strict-performance contract is enforced directly instead of only the currently checked subset.
